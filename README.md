# `async-google-apis`

This software generates asynchronous API stubs for Google APIs (and most likely
any other API described by a Discovery document). It uses
[`yup-oauth2`](https://github.com/dermesser/yup-oauth2) for the authorization
logic.

This project is still experimental. While for many complex APIs (Cloud Storage,
Drive v3, Sheets v4) usable APIs including types and documentation are generated
successfully, this doesn't mean that it will work on any other current or future
Google API.

## What it looks like

Consider the documentation of two exemplary APIs:

* [`drive:v3`](https://borgac.net/~lbo/doc/target/doc/drive_example/drive_v3_types/) for Google Drive.
* [`storage:v1`](https://borgac.net/~lbo/doc/target/doc/gcs_example/storage_v1_types/)
for Google Cloud Storage.

## Parts

* `manual_demo` is just a demo crate with some code for developers (well, me) to
experiment if the generated APIs work, and also to work manually with the Google
APIs to gain insights on which code to generate.

* `generate` contains a Python program fetching current Google Discovery documents
  (https://www.googleapis.com/discovery/v1/apis, see
   [documentation](https://developers.google.com/discovery/v1/reference)) and
  generating Rust code in the `generate/gen` directory. This is done very
  non-fancily using a few mustache templates and the `chevron` package. The script
  only takes two parameters, which you can discover using `--help`. In short, to
  generate an API stub for the API with ID `storage:v1` (Google Cloud Storage v1),
  run
  ```shell
  $ pipenv run ./generate.py --only_apis=storage:v1
  ```
  (install `pipenv` using `pip install --user pipenv` before, if you don't have it
  yet). See more details in that directory.
* Consult `drive_example` or `gcs_example` for simple but useful examples of
  using the generated code. As you can see, it is reasonably easy! Use `cargo doc`
  to generate the documentation for generated code, as the API comments is
  translated into Rust doc comments. I try keeping them up-to-date as the API of
  the generated code occasionally changes.
* `async-google-apis-common` contains shared code, for example the HTTP logic,
  used by the generated code, as well as some types (like errors) and as well as
  all imports. Include this crate in your dependencies when you are using
  the generated code in your project.
* NOTE: some parts of the API -- for example: URL query parameters that are not
  represented as enums -- may require small manual adjustments to the generated
  code. If possible, this should be solved automatically, but sometimes it isn't
  yet. Refer to the example crates for more details.


## To Do

* Integration tests: E.g. by writing a custom JSON service description and an
accompanying server binary to run test code against.
