#!/usr/bin/env python3

import argparse
import chevron
import json
import re
import requests

from os import path

from templates import *

def optionalize(name, optional=True):
    return 'Option<{}>'.format(name) if optional else name


def replace_keywords(name):
    return {
        'type': ('typ', 'type'),
    }.get(name, name)


def capitalize_first(name):
    return name[0].upper() + name[1:]


def snake_case(name):
    def r(c):
        if c.islower():
            return c
        return '_' + c.lower()

    return ''.join([r(c) for c in name])


def type_of_property(name, prop, optional=True):
    """Translate a JSON schema type into Rust types.

    Arguments:
        name: Name of the property. If the property is an object with fixed fields, generate a struct with this name.
        prop: A JSON object from a discovery document representing a type.

    Returns:
        type (string|tuple), structs (list of dicts)

        where type is a string representing a Rust type, or a tuple where the first element is a Rust type
        and the second element is a comment detailing the use of the field.
        The list of dicts returned as structs are any structs that need to be separately implemented and that
        the generated struct (if it was a struct) depends on.
    """
    typ = ''
    comment = ''
    structs = []
    try:
        if '$ref' in prop:
            return optionalize(prop['$ref'], optional), structs
        if 'type' in prop and prop['type'] == 'object':
            if 'properties' in prop:
                typ = name
                struct = {'name': name, 'fields': []}
                for pn, pp in prop['properties'].items():
                    subtyp, substructs = type_of_property(name + capitalize_first(pn), pp, optional=True)
                    if type(subtyp) is tuple:
                        subtyp, comment = subtyp
                    else:
                        comment = None
                    cleaned_pn = replace_keywords(pn)
                    if type(cleaned_pn) is tuple:
                        jsonname = cleaned_pn[1]
                        cleaned_pn = snake_case(cleaned_pn[0])
                    else:
                        jsonname = pn
                        cleaned_pn = snake_case(cleaned_pn)
                    struct['fields'].append({
                        'name':
                        cleaned_pn,
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
                structs.append(struct)
                return (optionalize(typ, optional), prop.get('description', '')), structs
            if 'additionalProperties' in prop:
                field, substructs = type_of_property(name, prop['additionalProperties'], optional=False)
                structs.extend(substructs)
                if type(field) is tuple:
                    typ = field[0]
                else:
                    typ = field
                return (optionalize('HashMap<String,' + typ + '>', optional), prop.get('description', '')), structs
        if prop['type'] == 'array':
            typ, substructs = type_of_property(name, prop['items'], optional=False)
            if type(typ) is tuple:
                typ = typ[0]
            return (optionalize('Vec<' + typ + '>', optional), prop.get('description', '')), structs + substructs
        if prop['type'] == 'string':
            if 'format' in prop:
                if prop['format'] == 'int64':
                    return (optionalize('String', optional), 'i64: ' + prop.get('description', '')), structs
                if prop['format'] == 'int32':
                    return (optionalize('String', optional), 'i32: ' + prop.get('description', '')), structs
                if prop['format'] == 'double':
                    return (optionalize('String', optional), 'f64: ' + prop.get('description', '')), structs
                if prop['format'] == 'float':
                    return (optionalize('String', optional), 'f32: ' + prop.get('description', '')), structs
                if prop['format'] == 'date-time':
                    return (optionalize('DateTime<Utc>', optional), prop.get('description', '')), structs
            return (optionalize('String', optional), prop.get('description', '')), structs
        if prop['type'] == 'boolean':
            return (optionalize('bool', optional), prop.get('description', '')), structs
        if prop['type'] in ('number', 'integer'):
            if prop['format'] == 'float':
                return (optionalize('f32', optional), prop.get('description', '')), structs
            if prop['format'] == 'double':
                return (optionalize('f64', optional), prop.get('description', '')), structs
            if prop['format'] == 'int32':
                return (optionalize('i32', optional), prop.get('description', '')), structs
            if prop['format'] == 'int64':
                return (optionalize('i64', optional), prop.get('description', '')), structs
        raise Exception('unimplemented!', name, prop)
    except KeyError as e:
        print(name, prop)
        print(e)
        raise e


def scalar_type(jsont):
    """Translate a scalar json type (for parameters) into Rust."""
    if jsont == 'boolean':
        return 'bool'
    elif jsont == 'string':
        return 'String'
    elif jsont == 'integer':
        return 'i64'
    raise Exception('unknown scalar type:', jsont)


def generate_parameter_types(resources):
    """Generate parameter structs from the resources list."""
    structs = []
    for resourcename, resource in resources.items():
        for methodname, method in resource['methods'].items():
            print(resourcename, methodname)
            struct = {'name': capitalize_first(resourcename) + capitalize_first(methodname) + 'Params', 'fields': []}
            if 'parameters' in method:
                for paramname, param in method['parameters'].items():
                    struct['fields'].append({
                        'name':
                        snake_case(paramname),
                        'typ':
                        optionalize(scalar_type(param['type']), not param.get('required', False)),
                        'comment':
                        param.get('description', ''),
                        'attr':
                        '#[serde(rename = "{}")]'.format(paramname),
                    })
            structs.append(struct)
    return structs


def resolve_parameters(string, paramsname='params', suffix=''):
    """Returns a Rust syntax for formatting the given string with API
    parameters, and a list of (snake-case) API parameters that are used. """
    pat = re.compile('\{(\w+)\}')
    params = re.findall(pat, string)
    snakeparams = [snake_case(p) for p in params]
    format_params = ','.join(['{}={}.{}{}'.format(p, paramsname, sp, suffix) for (p, sp) in zip(params, snakeparams)])
    return 'format!("{}", {})'.format(string, format_params), snakeparams


def generate_service(resource, methods, discdoc):
    """Generate the code for all methods in a resource."""
    service = capitalize_first(resource)

    parts = []

    method_fragments = []

    # Generate individual methods.
    for methodname, method in methods['methods'].items():
        params_name = service + capitalize_first(methodname) + 'Params'
        parameters = {p: snake_case(p) for p, pp in method.get('parameters', {}).items() if 'required' not in pp}
        in_type = method['request']['$ref'] if 'request' in method else '()'
        out_type = method['response']['$ref'] if 'response' in method else '()'
        is_upload = 'mediaUpload' in method
        media_upload = method.get('mediaUpload', None)
        if media_upload and 'simple' in media_upload['protocols']:
            upload_path = media_upload['protocols']['simple']['path']
        else:
            upload_path = ''
        http_method = method['httpMethod']

        formatted_path, required_params = resolve_parameters(method['path'])
        data_normal = {'name': methodname, 'param_type': params_name, 'in_type': in_type, 'out_type': out_type,
                'base_path': discdoc['baseUrl'], 'rel_path_expr': formatted_path,
                'params': [{'param': p, 'snake_param': sp} for (p, sp) in parameters.items()],
                'http_method': http_method}
        method_fragments.append(chevron.render(NormalMethodTmpl, data_normal))

        if is_upload:
            data_upload = {'name': snake_case(methodname), 'param_type': params_name, 'in_type': in_type, 'out_type': out_type,
                    'base_path': discdoc['rootUrl'], 'rel_path_expr': '"'+upload_path.lstrip('/')+'"',
                    'params': [{'param': p, 'snake_param': sp} for (p, sp) in parameters.items()],
                    'http_method': http_method}
            method_fragments.append(chevron.render(UploadMethodTmpl, data_upload))

    return chevron.render(ServiceImplementationTmpl,
            {'service': service,
             'methods': [{'text': t} for t in method_fragments]})


def generate_structs(discdoc):
    schemas = discdoc['schemas']
    resources = discdoc['resources']
    structs = []
    services = []
    for name, desc in schemas.items():
        typ, substructs = type_of_property(name, desc)
        structs.extend(substructs)

    # Generate parameter types.
    structs.extend(generate_parameter_types(resources))

    for resource, methods in resources.items():
        services.append(generate_service(resource, methods, discdoc))

    modname = (discdoc['id'] + '_types').replace(':', '_')
    with open(path.join('gen', modname + '.rs'), 'w') as f:
        f.write(RustHeader)
        for s in structs:
            for field in s['fields']:
                if field.get('comment', None):
                    field['comment'] = field['comment'].replace('\n', ' ')
            f.write(chevron.render(ResourceStructTmpl, s))
        for s in services:
            f.write(s)


def fetch_discovery_base(url, apis):
    '''Fetch the discovery base document from `url`. Return api documents for APIs with IDs in `apis`.

    Returns:
        List of API JSON documents.
    '''
    doc = json.loads(requests.get(url).text)
    return [it for it in doc['items'] if it['id'] in apis]


def fetch_discovery_doc(api_doc):
    url = api_doc['discoveryRestUrl']
    return json.loads(requests.get(url).text)


def main():
    p = argparse.ArgumentParser(description='Generate Rust code for asynchronous REST Google APIs.')
    p.add_argument('--discovery_base',
                   default='https://www.googleapis.com/discovery/v1/apis',
                   help='Base Discovery document.')
    p.add_argument('--only_apis', default='drive:v3', help='Only process APIs with these IDs (comma-separated)')
    args = p.parse_args()
    print(args.only_apis)
    docs = fetch_discovery_base(args.discovery_base, args.only_apis)
    for doc in docs:
        discdoc = fetch_discovery_doc(doc)
        #print(json.dumps(discdoc, sort_keys=True, indent=2))
        generate_structs(discdoc)


if __name__ == '__main__':
    main()
