use anyhow::Result;

fn main() {
    // p = argparse.ArgumentParser(description='Generate Rust code for asynchronous REST Google APIs.')
    // p.add_argument('--discovery_base',
    //                default='https://www.googleapis.com/discovery/v1/apis',
    //                help='Base Discovery document.')
    // p.add_argument('--only_apis', default='drive:v3', help='Only process APIs with these IDs (comma-separated)')
    // p.add_argument('--doc', default='', help='Directly process Discovery document from this URL')
    // p.add_argument('--list', default=False, help='List available APIs', action='store_true')

    // args = p.parse_args()

    // if args.only_apis:
    //     apilist = args.only_apis.split(',')
    // else:
    //     apilist = []

    // if args.list:
    //     docs = fetch_discovery_base(args.discovery_base, [])
    //     for doc in docs:
    //         print('API:', doc['title'], 'ID:', doc['id'])
    //     return

    // if args.doc:
    //     discdoc = fetch_discovery_doc(args.doc)
    //     if 'error' in discdoc:
    //         print('Error while fetching document for', doc['id'], ':', discdoc)
    //         return
    //     if 'methods' in discdoc:
    //         #raise NotImplementedError("top-level methods are not yet implemented properly. Please take care.")
    //         pass
    //     generate_all(discdoc)
    //     return

    // docs = fetch_discovery_base(args.discovery_base, apilist)

    // for doc in docs:
    //     try:
    //         discdoc = fetch_discovery_doc(doc['discoveryRestUrl'])
    //         if 'methods' in discdoc:
    //             raise NotImplementedError("top-level methods are not yet implemented properly. Please take care.")
    //         if 'error' in discdoc:
    //             print('Error while fetching document for', doc['id'], ':', discdoc)
    //             continue
    //         generate_all(discdoc)
    //     except Exception as e:
    //         print("Error while processing", discdoc)
    //         raise e
    //         continue
}
