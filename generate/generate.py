#!/usr/bin/env python3

import argparse
import chevron
import json
import requests

from os import path

ResourceStructTmpl = '''
#[derive(Serialize, Deserialize, Debug, Clone)]
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


def type_of_property(name, prop):
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
            return prop['$ref'], structs
        if 'type' in prop and prop['type'] == 'object':
            if 'properties' in prop:
                typ = name
                struct = {'name': name, 'fields': []}
                for pn, pp in prop['properties'].items():
                    subtyp, substructs = type_of_property(
                        name + capitalize_first(pn), pp)
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
                        '#[serde(rename = "{}")]'.format(jsonname),
                        'typ':
                        subtyp,
                        'comment':
                        comment
                    })
                    structs.extend(substructs)
                structs.append(struct)
                return typ, structs
            if 'additionalProperties' in prop:
                field, substructs = type_of_property(
                    name, prop['additionalProperties'])
                structs.extend(substructs)
                if type(field) is tuple:
                    typ = field[0]
                else:
                    typ = field
                print(typ)
                return 'HashMap<String,' + typ + '>', structs
        if prop['type'] == 'array':
            typ, substructs = type_of_property(name, prop['items'])
            if type(typ) is tuple:
                typ = typ[0]
            return 'Vec<' + typ + '>', structs + substructs
        if prop['type'] == 'string':
            if 'format' in prop:
                if prop['format'] == 'int64':
                    return ('String', 'i64'), structs
                if prop['format'] == 'int32':
                    return ('String', 'i32'), structs
                if prop['format'] == 'double':
                    return ('String', 'f64'), structs
                if prop['format'] == 'float':
                    return ('String', 'f32'), structs
                if prop['format'] == 'date-time':
                    return 'DateTime<Utc>', structs
            return 'String', structs
        if prop['type'] == 'boolean':
            return 'bool', structs
        if prop['type'] in ('number', 'integer'):
            if prop['format'] == 'float':
                return 'f32', structs
            if prop['format'] == 'double':
                return 'f64', structs
            if prop['format'] == 'int32':
                return 'i32', structs
            if prop['format'] == 'int64':
                return 'i64', structs
        raise Exception('unimplemented!', name, prop)
    except KeyError as e:
        print(name, prop)
        print(e)
        raise e


def generate_structs(discdoc):
    schemas = discdoc['schemas']
    structs = []
    for name, desc in schemas.items():
        typ, substructs = type_of_property(name, desc)
        structs.extend(substructs)

    modname = (discdoc['id'] + '_types').replace(':', '_')
    with open(path.join('gen', modname + '.rs'), 'w') as f:
        f.writelines([
            'use serde::{Deserialize, Serialize};\n',
            'use chrono::{DateTime, Utc};\n',
            'use std::collections::HashMap;\n'
            ])
        for s in structs:
            f.write(chevron.render(ResourceStructTmpl, s))


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
    p = argparse.ArgumentParser(
        description='Generate Rust code for asynchronous REST Google APIs.')
    p.add_argument('--discovery_base',
                   default='https://www.googleapis.com/discovery/v1/apis',
                   help='Base Discovery document.')
    p.add_argument('--only_apis',
                   default='drive:v3',
                   help='Only process APIs with these IDs (comma-separated)')
    args = p.parse_args()
    print(args.only_apis)
    docs = fetch_discovery_base(args.discovery_base, args.only_apis)
    for doc in docs:
        discdoc = fetch_discovery_doc(doc)
        #print(json.dumps(discdoc, sort_keys=True, indent=2))
        generate_structs(discdoc)


if __name__ == '__main__':
    main()
