# Google APIs Generator

This software generates asynchronous API stubs for Google APIs (and most likely
any other API described by a Discovery document). It uses
[`yup-oauth2`](https://github.com/dermesser/yup-oauth2) for the authorization
logic.

This project is still experimental. While for many complex APIs (Cloud Storage,
Drive v3, Sheets v4) usable APIs including types and documentation are generated
successfully, this doesn't mean that it will work on any other current or future
Google API.

## Usage

* `generate` contains a Python program fetching current Google Discovery documents
  (https://www.googleapis.com/discovery/v1/apis, see
   [documentation](https://developers.google.com/discovery/v1/reference)) and
  generating Rust code in the `src/gen` directory.
  To generate an API stub for the API with ID `storage:v1` (Google Cloud Storage
  v1):

  ```shell
  pipenv run ./generate.py --api=storage:v1
  ```

  (install `pipenv` using `pip install --user pipenv` before, if you don't have it
  yet). Use `--help` for more information.
* Consult `drive_example` or `gcs_example` for simple but useful examples of
  using the generated code. Use `cargo doc` to generate the documentation for
  generated code.
* NOTE: some parts of the API -- for example: URL query parameters that are not
  represented as enums -- may require small manual adjustments to the generated
  code. If possible, this should be solved automatically, but sometimes it isn't
  yet. Refer to the example crates for more details.

## To Do

* Integration tests: E.g. by writing a custom JSON service description and an
accompanying server binary to run test code against.
