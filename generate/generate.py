#!/usr/bin/env python3
#
# (c) 2020, 2021 Lewin Bormann <lbo@spheniscida.de>
#
# Please let me know about your use case of this code!
#
# Warning: This code is relatively hacky. It prefers working output over clean internal
# representation, partly due to the huge surface area of discovery documents.
# It is very possible that your preferred API doesn't work right away. However,
# despite its complications and recursions, the code is still somewhat hackable.
# Reach out to me if you need help!


import argparse
import chevron
import json
import re
import requests

import os
from os import path
from os import walk
import subprocess

from templates import *


def optionalize(name, optional=True):
    return 'Option<{}>'.format(name) if optional else name

# Rust keywords
keywords = {'as', 'break', 'const', 'continue', 'crate', 'else', 'enum', 'extern', 'false',
            'fn', 'for', 'if', 'impl', 'in', 'let', 'loop', 'match', 'mod', 'move', 'mut',
            'pub', 'ref', 'return', 'self', 'Self', 'static', 'struct', 'super', 'trait',
            'true', 'type', 'unsafe', 'use', 'where', 'while', 'async', 'await', 'abstract',
            'become', 'box', 'do', 'final', 'macro', 'override', 'priv', 'typeof', 'unsized',
            'virtual', 'try', 'yield', 'dyn', 'union', 'dyn'}

def replace_keywords(name):
    return name if name not in keywords else '_' + name


def capitalize_first(name):
    if len(name) == 0:
        return name
    return name[0].upper() + name[1:]


def sanitize_id(s):
    return s.replace('$', 'dollar').replace('#', 'hash').replace('.', '_').replace('@', 'at').replace('-', '_')


def rust_identifier(name):
    def r(c):
        if not c.isupper():
            return c
        return '_' + c.lower()
    return replace_keywords(''.join([(r(c) if i > 0 else c.lower()) for i, c in enumerate(sanitize_id(name))]))

def snake_to_camel(name):
    dest = []
    capitalize = True
    for c in name:
        if c == '_':
            capitalize = True
            continue
        if capitalize:
            dest.append(c.upper())
            capitalize = False
            continue
        dest.append(c)
    return ''.join(dest)


def global_params_name(api_name):
    return snake_to_camel(api_name + 'Params')


def parse_schema_types(name, schema, optional=True, parents=[]):
    """Translate a JSON schema type into Rust types, recursively.

    This function takes a schema entry from the `schemas` section of a Discovery document,
    and generates all Rust structs needed to represent the schema, recursively.

    Arguments:
        name: Name of the property. If the property is an object with fixed fields, generate a struct with this name.
        schema: A JSON object from a discovery document representing a type.

    Returns:
        (tuple, [dict], enums)

        where type is a tuple where the first element is a Rust type and the
        second element is a comment detailing the use of the field. The list of
        dicts returned as second element are any structs that need to be separately
        implemented and that the generated struct (if it was a struct) depends
        on. The dict contains elements as expected by templates.SchemaStructTmpl.
    """
    typ = ''
    comment = ''
    structs = []
    enums = []
    try:
        if '$ref' in schema:
            # We just assume that there is already a type generated for the reference.
            if schema['$ref'] not in parents:
                return optionalize(schema['$ref'], optional), structs, enums
            return optionalize('Box<' + schema['$ref'] + '>', optional), structs, enums
        if 'type' in schema and schema['type'] == 'object':
            # There are two types of objects: those with `properties` are translated into a Rust struct,
            # and those with `additionalProperties` into a HashMap<String, ...>.

            # Structs are represented as dicts that can be used to render the SchemaStructTmpl.
            if 'properties' in schema:
                name = replace_keywords(name)
                typ = name
                struct = {'name': name, 'description': schema.get('description', ''), 'fields': []}
                for pn, pp in schema['properties'].items():
                    subtyp, substructs, subenums = parse_schema_types(name + capitalize_first(pn),
                                                                      pp,
                                                                      optional=True,
                                                                      parents=parents + [name])
                    if type(subtyp) is tuple:
                        subtyp, comment = subtyp
                    else:
                        comment = None
                    cleaned_pn = replace_keywords(pn)
                    jsonname = pn
                    cleaned_pn = rust_identifier(cleaned_pn)
                    struct['fields'].append({
                        'name':
                        cleaned_pn,
                        'original_name':
                        jsonname,
                        'attr':
                        '#[serde(rename = "{}")]'.format(jsonname) +
                        '\n    #[serde(skip_serializing_if = "Option::is_none")]'
                        if subtyp.startswith('Option') else '',
                        'typ':
                        subtyp,
                        'comment':
                        comment
                    })
                    structs.extend(substructs)
                    enums.extend(subenums)
                structs.append(struct)
                return (optionalize(typ, optional), schema.get('description', '')), structs, enums

            if 'additionalProperties' in schema:
                field, substructs, subenums = parse_schema_types(name,
                                                                 schema['additionalProperties'],
                                                                 optional=False,
                                                                 parents=parents + [name])
                structs.extend(substructs)
                if type(field) is tuple:
                    typ = field[0]
                else:
                    typ = field
                return (optionalize('HashMap<String,' + typ + '>', optional), schema.get('description',
                                                                                         '')), structs, subenums

        if schema['type'] == 'array':
            typ, substructs, subenums = parse_schema_types(name,
                                                           schema['items'],
                                                           optional=False,
                                                           parents=parents + [name])
            if type(typ) is tuple:
                typ = typ[0]
            return (optionalize('Vec<' + typ + '>', optional), schema.get('description',
                                                                          '')), structs + substructs, subenums

        if schema['type'] == 'string':

            # Builds a line of a rust type
            def build(intt, typ='String'):
                return (optionalize(typ, optional), intt + ': ' + schema.get('description', '')), structs, enums

            if 'format' in schema:
                if schema['format'] == 'int64':
                    return build('i64')
                if schema['format'] == 'int32':
                    return build('i32')
                if schema['format'] == 'uint64':
                    return build('u64')
                if schema['format'] == 'uint32':
                    return build('u32')
                if schema['format'] == 'double':
                    return build('f64')
                if schema['format'] == 'float':
                    return build('f32')
                if schema['format'] == 'date-time':
                    return build('DateTime', typ='DateTime<Utc>')

            if 'enum' in schema and name:
                name_ = (sanitize_id(name))

                def sanitize_enum_value(v):
                    v = replace_keywords(capitalize_first(sanitize_id(v)))
                    if v[0].isnumeric():
                        v = '_' + v
                    return v

                values = [{
                    'line': sanitize_enum_value(ev),
                    'jsonvalue': ev,
                    'desc': schema.get('enumDescriptions', [''] * (i))[i]
                } for (i, ev) in enumerate(schema.get('enum', []))]
                templ_params = {'name': name_, 'values': values}
                return (optionalize(name_, optional), schema.get('description', '')), structs, [templ_params]

            return (optionalize('String', optional), schema.get('description', '')), structs, enums

        if schema['type'] == 'boolean':
            return (optionalize('bool', optional), schema.get('description', '')), structs, enums

        if schema['type'] in ('number', 'integer'):

            def build(intt):
                return (optionalize(intt, optional), schema.get('description', '')), structs, enums

            if schema['format'] == 'float':
                return build('f32')
            if schema['format'] == 'double':
                return build('f64')
            if schema['format'] == 'int32':
                return build('i32')
            if schema['format'] == 'int64':
                return build('i64')
            if schema['format'] == 'uint32':
                return build('u32')
            if schema['format'] == 'uint64':
                return build('u64')

        if schema['type'] == 'any':
            return (optionalize('String', optional), 'ANY data: ' + schema.get('description', '')), structs, enums

        raise Exception('unimplemented schema type!', name)
    except KeyError as e:
        print('KeyError while processing:', name)
        raise e


def generate_params_structs(resources, super_name='', global_params=None):
    """Generate parameter structs and enums from the resources list.

    Every resource usually has a set of parameters, which are translated into a
    Rust struct by this function. Any enum types are extracted and represented
    as enums.

    Parameter types also come with a `Display` implementation.

    Returns a tuple of (struct template dicts, enum template dicts).

    The struct template dicts are to be rendered using the SchemaStructTmpl,
    the enum template dicts need to be rendered with the SchemaEnumTmpl
    template.
    """
    frags = []
    structs = []
    enums = []
    for resourcename, resource in resources.items():
        for methodname, method in resource.get('methods', {}).items():
            param_type_name = snake_to_camel(super_name + capitalize_first(resourcename) +
                                             capitalize_first(methodname) + 'Params')
            print("processed:", resourcename, methodname, param_type_name)
            struct = {
                'name': param_type_name,
                'description': 'Parameters for the `{}.{}` method.'.format(resourcename, methodname),
                'fields': []
            }
            req_query_parameters = []
            opt_query_parameters = []
            if global_params:
                struct['fields'].append({
                    'name': rust_identifier(global_params),
                    'typ': optionalize(global_params, True),
                    'attr': '#[serde(flatten)]',
                    'comment': 'General attributes applying to any API call'
                })
            # Build struct dict for rendering.
            if 'parameters' in method:
                for paramname, param in method['parameters'].items():
                    (typ, desc), substructs, subenums = parse_schema_types(capitalize_first(resourcename)+capitalize_first(methodname)+capitalize_first(paramname),
                            param, optional=False, parents=[])
                    enums.extend(subenums)
                    field = {
                        'name': rust_identifier(paramname),
                        'original_name': paramname,
                        'typ': optionalize(typ, not param.get('required', False)),
                        'comment': desc,
                        'attr': '#[serde(rename = "{}")]'.format(paramname),
                    }
                    struct['fields'].append(field)
                    if param.get('location', '') == 'query':
                        if param.get('required', False):
                            req_query_parameters.append(field)
                        else:
                            opt_query_parameters.append(field)
            frags.append(chevron.render(SchemaStructTmpl, struct))
            struct['required_fields'] = req_query_parameters
            struct['optional_fields'] = opt_query_parameters
            frags.append(chevron.render(SchemaDisplayTmpl, struct))
            structs.append(struct)
        # Generate parameter types for subresources.
        subfrags, subenums = generate_params_structs(resource.get('resources', {}),
                super_name=super_name + '_' + resourcename,
                global_params=global_params)
        frags.extend(subfrags)
        enums.extend(subenums)
        structs.extend(subfrags)
    return structs, enums


def resolve_parameters(string, paramsname='params'):
    """Returns a Rust syntax for formatting the given string with API
    parameters, and a list of (snake-case) API parameters that are used. This
    is typically used to format URL paths containing required parameters for an
    API call.
    """
    pat = re.compile('\{\+?(\w+)\}')
    params = re.findall(pat, string)
    snakeparams = [rust_identifier(p) for p in params]
    format_params = ','.join([
        '{}=percent_encode(format!("{{}}", {}.{}).as_bytes(), NON_ALPHANUMERIC)'.format(p, paramsname, sp)
        for (p, sp) in zip(params, snakeparams)
    ])
    string = string.replace('{+', '{')
    # Some required parameters are in the URL. This rust syntax formats the relative URL part appropriately.
    return 'format!("{}", {})'.format(string, format_params), snakeparams


def generate_service(resource, methods, discdoc, generate_subresources=True):
    """Generate the code for all methods in a resource.

    Returns a rendered string with source code.
    """
    service = capitalize_first(snake_to_camel(rust_identifier(resource)))
    # Source code fragments implementing the methods.
    method_fragments = []
    # Source code fragments for impls of subordinate resources.
    subresource_fragments = []

    # Generate methods for subresources.
    if generate_subresources:
        for subresname, subresource in methods.get('resources', {}).items():
            subresource_fragments.append(generate_service(service + capitalize_first(subresname), subresource, discdoc))

    for methodname, method in methods.get('methods', {}).items():
        # Goal: Instantiate the templates for upload and non-upload methods.

        # e.g. FilesGetParams
        params_type_name = service + capitalize_first(methodname) + 'Params'
        # All parameters that are optional (as URL parameters)
        parameters = {
            p: rust_identifier(p)
            for p, pp in method.get('parameters', {}).items() if ('required' not in pp and pp['location'] != 'path')
        }
        # All required parameters not represented in the path.
        required_parameters = {
            p: rust_identifier(p)
            for p, pp in method.get('parameters', {}).items() if ('required' in pp and pp['location'] != 'path')
        }
        # Types of the function
        in_type = method['request']['$ref'] if 'request' in method else None
        out_type = method['response']['$ref'] if 'response' in method else '()'

        is_download = method.get('supportsMediaDownload', False)
        is_authd = 'scopes' in method

        media_upload = method.get('mediaUpload', {})
        supported_uploads = []
        if 'simple' in media_upload.get('protocols', {}):
            simple_upload_path = media_upload['protocols']['simple']['path']
            supported_uploads.append('simple')
        else:
            simple_upload_path = ''
        if 'resumable' in media_upload.get('protocols', {}):
            resumable_upload_path = media_upload['protocols']['resumable']['path']
            supported_uploads.append('resumable')
        else:
            resumable_upload_path = ''

        http_method = method['httpMethod']
        has_global_params = 'parameters' in discdoc
        # This relies on URL path parameters being required parameters (not
        # optional). If this invariant is not fulfilled, the Rust code may not
        # compile.
        formatted_path, required_params = resolve_parameters(method['path'])
        formatted_simple_upload_path, required_params = resolve_parameters(simple_upload_path)
        formatted_resumable_upload_path, required_params = resolve_parameters(resumable_upload_path)

        # Guess default scope.
        scopetype, scopeval = scopes_url_to_enum_val(discdoc['name'], method.get('scopes', [''])[-1])
        scope_enum = scopetype + '::' + scopeval

        if is_download:
            data_download = {
                'name':
                rust_identifier(methodname),
                'param_type':
                params_type_name,
                'in_type':
                in_type,
                'download_in_type':
                in_type if in_type else 'EmptyRequest',
                'out_type':
                out_type,
                'base_path':
                discdoc['baseUrl'],
                'root_path':
                discdoc['rootUrl'],
                'rel_path_expr':
                formatted_path,
                'params': [{
                    'param': p,
                    'snake_param': sp
                } for (p, sp) in parameters.items()],
                'required_params': [{
                    'param': p,
                    'snake_param': sp
                } for (p, sp) in required_parameters.items()],
                'global_params_name':
                rust_identifier(global_params_name(discdoc.get('name', ''))) if has_global_params else None,
                'scopes': [{
                    'scope': scope_enum,
                }],
                'description':
                method.get('description', '').replace('\n', '\n/// '),
                'http_method':
                http_method,
                'wants_auth':
                is_authd,
            }
            method_fragments.append(chevron.render(DownloadMethodTmpl, data_download))
        else:
            data_normal = {
                'name':
                rust_identifier(methodname),
                'param_type':
                params_type_name,
                'in_type':
                in_type,
                'out_type':
                out_type,
                'base_path':
                discdoc['baseUrl'],
                'root_path':
                discdoc['rootUrl'],
                'rel_path_expr':
                formatted_path,
                'params': [{
                    'param': p,
                    'snake_param': sp
                } for (p, sp) in parameters.items()],
                'global_params_name':
                rust_identifier(global_params_name(discdoc.get('name', ''))) if has_global_params else None,
                'required_params': [{
                    'param': p,
                    'snake_param': sp
                } for (p, sp) in required_parameters.items()],
                'scopes': [{
                    'scope': scope_enum,
                }],
                'description':
                method.get('description', '').replace('\n', '\n/// '),
                'http_method':
                http_method,
                'wants_auth':
                is_authd,
            }
            method_fragments.append(chevron.render(NormalMethodTmpl, data_normal))

        # We generate an additional implementation with the option of uploading data.
        data_upload = {
            'name': rust_identifier(methodname),
            'param_type': params_type_name,
            'in_type': in_type,
            'out_type': out_type,
            'base_path': discdoc['baseUrl'],
            'root_path': discdoc['rootUrl'],
            'simple_rel_path_expr': formatted_simple_upload_path.lstrip('/'),
            'resumable_rel_path_expr': formatted_resumable_upload_path.lstrip('/'),
            'global_params_name':
            rust_identifier(global_params_name(discdoc.get('name', ''))) if has_global_params else None,
            'params': [{
                'param': p,
                'snake_param': sp
            } for (p, sp) in parameters.items()],
            'required_params': [{
                'param': p,
                'snake_param': sp
            } for (p, sp) in required_parameters.items()],
            'scopes': [{
                'scope': scope_enum,
            }],
            'description': method.get('description', '').replace('\n', '\n/// '),
            'http_method': http_method,
            'wants_auth': is_authd,
        }
        if 'simple' in supported_uploads:
            method_fragments.append(chevron.render(UploadMethodTmpl, data_upload))
        if 'resumable' in supported_uploads:
            method_fragments.append(chevron.render(ResumableUploadMethodTmpl, data_upload))

    return chevron.render(
        ServiceImplementationTmpl, {
            'service': service,
            'name': rust_identifier(capitalize_first(discdoc.get('name', ''))),
            'base_path': discdoc['baseUrl'],
            'root_path': discdoc['rootUrl'],
            'wants_auth': 'auth' in discdoc,
            'methods': [{
                'text': t
            } for t in method_fragments]
        }) + '\n'.join(subresource_fragments)


def scopes_url_to_enum_val(apiname, url):
    split = url.split('/')
    rawname = split[-1]
    if len(rawname) == 0 and len(split) > 1:
        rawname = split[-2]
    fancy_name = snake_to_camel(rawname.replace('-', '_').replace('.', '_'))
    return (snake_to_camel(apiname) + 'Scopes', fancy_name)


def generate_scopes_type(name, scopes):
    """Generate types for the `scopes` dictionary (path: auth.oauth2.scopes in a discovery document),
    containing { scope_url: { description: "..." } }.
    """
    if len(scopes) == 0:
        return ''
    parameters = {'scopes': []}
    for url, desc in scopes.items():
        enum_type_name, fancy_name = scopes_url_to_enum_val(name, url)
        parameters['name'] = enum_type_name
        parameters['scopes'].append({'scope_name': fancy_name, 'desc': desc.get('description', ''), 'url': url})
    return chevron.render(OauthScopesType, parameters)


def struct_inline_comments(s):
    for field in s['fields']:
        if field.get('comment', None):
            field['comment'] = field.get('comment', '').replace('\n', '\n/// ')
    if s.get('desc', None):
        s['desc'] = s.get('desc', '').replace('\n', '\n/// ')
    if s.get('description', None):
        s['description'] = s.get('description', '').replace('\n', '\n/// ')

def enum_inline_comments(e):
    for value in e.get('values', {}):
        if value.get('desc', None):
            value['desc'] = value.get('desc', '').replace('\n', '\n/// ')
    for value in e.get('scopes', {}):
        if value.get('desc', None):
            value['desc'] = value.get('desc', '').replace('\n', '\n/// ')

def generate_all(discdoc):
    """Generate all structs and impls, and render them into a file."""
    print('Processing:', discdoc.get('id', ''))
    schemas = discdoc.get('schemas', {})
    resources = discdoc.get('resources', {})
    # Generate scopes.
    scopes_type = generate_scopes_type(discdoc['name'], discdoc.get('auth', {}).get('oauth2', {}).get('scopes', {}))

    # Generate parameter types (*Params - those are used as "side inputs" to requests)
    params_struct_name = global_params_name(discdoc.get('name'))
    parameter_types, parameter_enums = generate_params_structs(resources, global_params=params_struct_name)

    # Generate service impls.
    services = []
    for resource, methods in resources.items():
        services.append(generate_service(resource, methods, discdoc))
    if 'methods' in discdoc:
        services.append(generate_service('Global', discdoc, discdoc, generate_subresources=False))

    # Generate schema types.
    structs = []
    enums = []
    for name, desc in schemas.items():
        typ, substructs, subenums = parse_schema_types(name, desc)
        structs.extend(substructs)
        enums.extend(subenums)

    # Generate global parameters struct and its Display impl.
    if 'parameters' in discdoc:
        schema = {'type': 'object', 'properties': discdoc['parameters']}
        name = replace_keywords(snake_to_camel(params_struct_name))
        typ, substructs, subenums = parse_schema_types(name, schema)
        for s in substructs:
            s['optional_fields'] = s['fields']
        parameter_types.extend(substructs)
        parameter_enums.extend(subenums)

    # Assemble everything into a file.
    modname = (discdoc['id'] + '_types').replace(':', '_').replace('.', '_')
    out_path = path.join('../src/gen', modname + '.rs')
    with open(out_path, 'w') as f:
        f.write(RustHeader)
        f.write(scopes_type)
        # Render resource structs.
        for s in structs:
            struct_inline_comments(s)
            if not s['name']:
                print('WARN', s)
            f.write(chevron.render(SchemaStructTmpl, s))
        for e in enums:
            enum_inline_comments(e)
            f.write(chevron.render(SchemaEnumTmpl, e))
        for e in parameter_enums:
            enum_inline_comments(e)
            f.write(chevron.render(SchemaEnumTmpl, e))
        # Render *Params structs.
        for pt in parameter_types:
            struct_inline_comments(pt)
            f.write(chevron.render(SchemaStructTmpl, pt))
            f.write(chevron.render(SchemaDisplayTmpl, pt))
        # Render service impls.
        for s in services:
            f.write(s)
    try:
        subprocess.run(['rustfmt', out_path, '--edition=2018'])
    except:
        return



def from_cache(apiId):
    try:
        with open(path.join('cache', apiId + '.json'), 'r') as f:
            print('Found API description in cache for', apiId)
            return json.load(f)
    except Exception as e:
        print('Fetching description from cache failed:', e)
        return None


def to_cache(apiId, doc):
    try:
        os.makedirs('cache', exist_ok=True)
        with open(path.join('cache', apiId + '.json'), 'w') as f:
            json.dump(doc, f)
    except Exception as e:
        print(e)
        return None
    return None


def fetch_discovery_base(url, apis):
    """Fetch the discovery base document from `url`. Return api documents for APIs with IDs in `apis`.

    Returns:
        List of API JSON documents.
    """
    doc = from_cache('_global_discovery')
    if not doc:
        doc = json.loads(requests.get(url).text)
        to_cache('_global_discovery', doc)
    return [it for it in doc['items'] if (not apis or it['id'] in apis)]


def fetch_discovery_doc(url_or_path):
    """Fetch discovery document for a given (short) API doc from the overall discovery document."""
    cachekey = url_or_path.replace('/', '_')
    cached = from_cache(cachekey)
    if cached:
        return cached

    if url_or_path.startswith('http'):
        js = json.loads(requests.get(url_or_path).text)
        to_cache(cachekey, js)
    else:
        with open(url_or_path, 'r') as f:
            js = json.load(f)
    return js


def main():
    p = argparse.ArgumentParser(description='Generate Rust code for asynchronous REST Google APIs.')
    p.add_argument('--discovery_base',
                   default='https://www.googleapis.com/discovery/v1/apis',
                   help='Base Discovery document.')
    p.add_argument('--apis', default='drive:v3', help='Only process APIs with these IDs (comma-separated)')
    p.add_argument('--doc', default='', help='Directly process Discovery document from this URL')
    p.add_argument('--list', default=False, help='List available APIs', action='store_true')

    args = p.parse_args()

    if args.apis:
        apilist = args.apis.split(',')
    else:
        apilist = []

    if args.list:
        docs = fetch_discovery_base(args.discovery_base, [])
        for doc in docs:
            print('API:', doc['title'], 'ID:', doc['id'])
        return

    if args.doc:
        discdoc = fetch_discovery_doc(args.doc)
        if 'error' in discdoc:
            print('Error while fetching document for', doc['id'], ':', discdoc)
            return
        if 'methods' in discdoc:
            #raise NotImplementedError("top-level methods are not yet implemented properly. Please take care.")
            pass
        generate_all(discdoc)
        return

    docs = fetch_discovery_base(args.discovery_base, apilist)

    for doc in docs:
        try:
            discdoc = fetch_discovery_doc(doc['discoveryRestUrl'])
            if 'methods' in discdoc:
                raise NotImplementedError("top-level methods are not yet implemented properly. Please take care.")
            if 'error' in discdoc:
                print('Error while fetching document for', doc['id'], ':', discdoc)
                continue
            generate_all(discdoc)
        except Exception as e:
            print("Error while processing discovery doc")
            # raise e
            continue

    _, _, mods_name = next(walk('../src/gen'))
    mod_rs_file = open('../src/gen/mod.rs', 'w+')
    for mod in mods_name:
        if mod == 'mod.rs' or re.match(".*\.rs", mod) == None:
            continue
        mod_name_line = 'pub mod ' + mod[:-3] + ';\n'
        mod_rs_file.write(mod_name_line)
    mod_rs_file.close()


if __name__ == '__main__':
    main()
