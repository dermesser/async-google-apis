# async-google-apis: Generator

This python script (collection) generates Rust code from Google's API discovery
documents. The easiest way to use the code is to copy the generated code to your
crate.

Make sure to import the `async-google-apis-common` crate in your `Cargo.toml`.
Please read the `README` in that crate for further advice.

* To generate an API listed in the global discovery document (specified by
    `--discovery_base`, which defaults to Google's at https://www.googleapis.com/discovery/v1/apis):
  ```bash
     generate.py --only_apis=api_id:v1
  ```
* To list all available APIs from the global discovery document:
  ```bash
     generate.py --list
  ```
* To generate an API that is not listed in the global discovery document:
  ```bash
     generate.py --doc=https://www.googleapis.com/discovery/v1/apis/photoslibrary/v1/rest
  ```

You can either include the code directly in your crate or generate a separate
one. The latter approach has the upside of not requiring lengthy recompilation:
Many Google APIs comprise one or several tens of thousands of lines of rust
code, which rustc has a hard time keeping up with.
