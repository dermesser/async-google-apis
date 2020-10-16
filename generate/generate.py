#!/usr/bin/env python3

import argparse
import chevron
import json
import requests

ResourceStructTmpl = '''
pub struct {name} {{
    {{#fields}}
        {{name}}: {{typ}},
    {{/fields}}
}}
'''

def json_type_to_rust_field(prop):
    if prop is None:
        return ''
    print(prop)
    if 'type' in prop:
        jt = prop['type']
    else:
        jt = 'object'

    if jt == 'string':
        if 'format' in prop:
            if prop['format'] in ['int64', 'int32']:
                return 'i64'
            if prop['format'] == 'date-time':
                return 'Time'
            if prop['format'] in ['float', 'double']:
                return 'float64'
            if prop['format'] == 'byte':
                return 'Vec<u8>'
        return 'String'
    if jt == 'boolean':
        return 'bool'
    if jt == 'array':
        inner = prop['items']
        inner_type = json_type_to_rust_field(inner)
        return 'Vec<' + inner_type + '>'
    if jt == 'object':
        if 'additionalProperties' in prop:
            inner = prop.get('additionalProperties', None)
            inner_type = json_type_to_rust_field(inner)
            return 'HashMap<String,'+inner_type+'>'
        else:
            for subpropname, subprop in prop.items():
                pass

def generate_structs(discdoc):
    schemas = discdoc['schemas']
    for name, desc in schemas.items():
        for propname, prop in desc['properties'].items():
            print(propname, '=>', json_type_to_rust_field(prop))


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
    p.add_argument('--discovery_base', default='https://www.googleapis.com/discovery/v1/apis', help='Base Discovery document.')
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
