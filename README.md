# `async-google-apis`

This software generates asynchronous API stubs for Google APIs (and most likely
any other API described by a Discovery document). It uses
[`yup-oauth2`](https://github.com/dermesser/yup-oauth2) for the authorization
logic.

This project is still experimental. While for many complex APIs (Cloud Storage,
Drive v3, Sheets v4) usable APIs including types and documentation are generated
successfully, this doesn't mean that it will work on any other current or future
Google API.

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
  yet)
* Consult `drive_example` for a simple but useful example of using the generated
  code. As you can see, it is reasonably easy! Use `cargo doc` to generate the
  documentation for generated code, as the API comments is translated into Rust
  doc comments.
* `async-google-apis-common` contains shared code, for example the HTTP logic,
  used by the generated code, as well as some types (like errors) and as well as
  all imports. Include this crate in your dependencies when you are using
  the generated code in your project.

## To Do

* Don't always fetch all fields. Currently, the parameter `&fields=*` is sent
with every request, which guarantees a full response, but not the best
performance.
* Multipart uploads are not yet supported. As a crutch, uploadable API endpoints
are defined using two methods: `method()` and `method_upload()`, where
`method_upload()` only uploads data, and `method()` only works with metadata.
This works at least for my favorite API, the Google Drive API (v3). @Byron has a
simple implementation of multipart HTTP in his excellent
[Byron/google-apis-rs](https://github.com/Byron/google-apis-rs) crate; something
similar may be useful here.
