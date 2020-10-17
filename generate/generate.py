#!/usr/bin/env python3

import argparse
import chevron
import json
import re
import requests

from os import path

ResourceStructTmpl = '''
#[derive(Serialize, Deserialize, Debug, Clone, Default)]
pub struct {{name}} {
{{#fields}}
    {{#comment}}
    // {{comment}}
    {{/comment}}
    {{{attr}}}
    {{name}}: {{{typ}}},
{{/fields}}
}
'''


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
                        'name': cleaned_pn,
                        'attr': '#[serde(rename = "{}")]'.format(jsonname),
                        'typ': subtyp,
                        'comment': comment
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

def resolve_parameters(string, paramsname='params', suffix='.unwrap()'):
    """Returns a Rust syntax for formatting the given string with API
    parameters, and a list of (snake-case) API parameters that are used. """
    pat = re.compile('\{(\w+)\}')
    params = re.findall(pat, string)
    snakeparams = [snake_case(p) for p in params]
    format_params = ','.join(['{}={}.{}{}'.format(p, paramsname, sp, suffix) for (p, sp) in zip(params, snakeparams)])
    return 'format!("{}", {})'.format(string, format_params), snakeparams

def generate_service(resource, methods, discdoc):
    service = capitalize_first(resource)

    parts = []
    parts.append('pub struct {}Service {{'.format(service))
    parts.append('  client: TlsClient,')
    parts.append('  authenticator: Authenticator,')
    parts.append('}')
    parts.append('')

    parts.append('impl {}Service {{'.format(service))

    for methodname, method in methods['methods'].items():
        params_name = service+capitalize_first(methodname)+'Params'
        in_type = method['request']['$ref'] if 'request' in method else '()'
        out_type = method['response']['$ref'] if 'response' in method else '()'
        is_upload = 'mediaUpload' in method

        if is_upload:
            parts.append('  fn {}(&mut self, params: {}, req: {}) -> Result<{}> {{'.format(
                snake_case(methodname), params_name, in_type, out_type))
        else:
            parts.append('  fn {}(&mut self, params: {}, req: {}, data: &hyper::body::Bytes) -> Result<{}> {{'.format(
                snake_case(methodname), params_name, in_type, out_type))

        formatted_path, required_params = resolve_parameters(method['path'])
        for rp in required_params:
            parts.append('    if params.{}.is_none() {{'.format(rp))
            parts.append('      return Err(Error::new(ApiError::InputDataError("Parameter {} is missing!".to_string())));'.format(rp))
            parts.append('    }')
        parts.append('    let relpath = {};'.format(formatted_path))
        parts.append('    unimplemented!()')
        parts.append('  }')

    parts.append('}')
    parts.append('')

    return '\n'.join(parts)


def generate_structs(discdoc):
    schemas = discdoc['schemas']
    resources = discdoc['resources']
    structs = []
    services = []
    for name, desc in schemas.items():
        typ, substructs = type_of_property(name, desc)
        structs.extend(substructs)
    for name, res in resources.items():
        for methodname, method in res['methods'].items():
            if 'parameters' not in method:
                structs.append({
                    'name': '{}{}Params'.format(capitalize_first(name), capitalize_first(methodname)),
                    'fields': []
                })
            else:
                params = method['parameters']
                typ = {'type': 'object', 'properties': params}
                typ, substructs = type_of_property(
                    '{}{}Params'.format(capitalize_first(name), capitalize_first(methodname)), typ)
                structs.extend(substructs)

    for resource, methods in resources.items():
        services.append(generate_service(resource, methods, discdoc))

    modname = (discdoc['id'] + '_types').replace(':', '_')
    with open(path.join('gen', modname + '.rs'), 'w') as f:
        f.writelines([
            'use serde::{Deserialize, Serialize};\n',
            'use chrono::{DateTime, Utc};\n',
            'use anyhow::{Error, Result};\n',
            'use std::collections::HashMap;\n',
            '''
type TlsConnr = hyper_rustls::HttpsConnector<hyper::client::HttpConnector>;
type TlsClient = hyper::Client<TlsConnr, hyper::Body>;
type Authenticator = yup_oauth2::authenticator::Authenticator<TlsConnr>;

#[derive(Debug, Clone)]
pub enum ApiError {
  InputDataError(String),
}

impl std::error::Error for ApiError {}
impl std::fmt::Display for ApiError {
  fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
    std::fmt::Debug::fmt(self, f)
  }
}
''',
        ])
        for s in structs:
            for field in s['fields']:
                if field.get('comment', None):
                    field['comment'] = field['comment'].replace('\n', ' ')
            f.write(chevron.render(ResourceStructTmpl, s))
        for s in services:
            f.write(s)
            f.write('\n')


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
