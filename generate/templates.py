# General imports and error type.
RustHeader = '''
#![allow(unused_variables, unused_mut, dead_code)]
//! This file was generated by async-google-apis. (https://github.com/dermesser/async-google-apis)
//!
//! (c) 2020 Lewin Bormann <lbo@spheniscida.de>
//!
//! ## Getting started
//! 
//! **Tip**: Take a look at those types ending in `...Service`. These represent API resources
//! and contain methods to interact with an API. The remaining types are used by those methods
//! and can be explored starting from a method you want to use.
//!
//! I'd be happy if you let me know about your use case of this code.
//!
//! THIS FILE HAS BEEN GENERATED -- SAVE ANY MODIFICATIONS BEFORE REPLACING.

use async_google_apis_common::*;
'''

# Dict contents --
# name (of API, Capitalized)
# scopes: [{name, url, desc}]
OauthScopesType = '''
/// Scopes of this API. Convertible to their string representation with `AsRef`.
#[derive(Debug, Clone, Copy)]
pub enum {{{name}}}Scopes {
    {{#scopes}}
    /// {{{desc}}}
    ///
    /// URL: {{{url}}}
    {{{scope_name}}},
    {{/scopes}}
}

impl std::convert::AsRef<str> for {{{name}}}Scopes {
    fn as_ref(&self) -> &'static str {
        match self {
            {{#scopes}}
            {{{name}}}Scopes::{{{scope_name}}} => "{{{url}}}",
            {{/scopes}}
        }
    }
}

'''

# A struct for parameters or input/output API types.
# Dict contents --
# name
# fields: [{name, comment, attr, typ}]
SchemaStructTmpl = '''
/// {{{description}}}
#[derive(Serialize, Deserialize, Debug, Clone, Default)]
pub struct {{{name}}} {
{{#fields}}
    {{#comment}}
    /// {{{comment}}}
    {{/comment}}
    {{#attr}}
    {{{attr}}}
    {{/attr}}
    pub {{{name}}}: {{{typ}}},
{{/fields}}
}
'''

# Serialize a global params struct to a URL query string.
SchemaDisplayTmpl = '''
impl std::fmt::Display for {{{name}}} {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        {{#required_fields}}
        write!(f, "&{{{original_name}}}={}", percent_encode(format!("{}", self.{{{name}}}).as_bytes(), NON_ALPHANUMERIC).to_string())?;
        {{/required_fields}}
        {{#optional_fields}}
        if let Some(ref v) = self.{{{name}}} {
            write!(f, "&{{{original_name}}}={}", percent_encode(format!("{}", v).as_bytes(), NON_ALPHANUMERIC).to_string())?;
        }
        {{/optional_fields}}
        Ok(())
    }
}
'''

# Dict contents --
#
# api, service (names: e.g. Files)
# methods: [{text}] (the method implementations as {'text': ...} dicts)
# name (API name)
ServiceImplementationTmpl = '''
/// The {{{name}}} {{{service}}} service represents the {{{service}}} resource.
pub struct {{{service}}}Service {
    client: TlsClient,
    authenticator: Box<dyn 'static + std::ops::Deref<Target=Authenticator>>,
    scopes: Vec<String>,
}

impl {{{service}}}Service {
    /// Create a new {{service}}Service object. The easiest way to call this is wrapping the Authenticator
    /// into an `Rc`: `new(client.clone(), Rc::new(authenticator))`.
    /// This way, one authenticator can be shared among several services.
    pub fn new<A: 'static + std::ops::Deref<Target=Authenticator>>(client: TlsClient, auth: A) -> {{service}}Service {
        {{{service}}}Service { client: client, authenticator: Box::new(auth), scopes: vec![] }
    }

    /// Explicitly select which scopes should be requested for authorization. Otherwise,
    /// a possibly too large scope will be requested.
    ///
    /// It is most convenient to supply a vec or slice of {{{name}}}Scopes enum values.
    pub fn set_scopes<S: AsRef<str>, T: AsRef<[S]>>(&mut self, scopes: T) {
        self.scopes = scopes.as_ref().into_iter().map(|s| s.as_ref().to_string()).collect();
    }

    {{#methods}}
{{{text}}}
    {{/methods}}
}
'''

# Takes dict contents:
# name, description, param_type, in_type, out_type
# base_path, rel_path_expr, scopes (string repr. of rust string array),
# params: [{param, snake_param}]
# http_method
NormalMethodTmpl = '''
/// {{{description}}}
pub async fn {{{name}}}(
    &mut self, params: &{{{param_type}}}{{#in_type}}, req: &{{{in_type}}}{{/in_type}}) -> Result<{{{out_type}}}> {

    let rel_path = {{{rel_path_expr}}};
    let path = "{{{base_path}}}".to_string() + &rel_path;
    let tok;
    if self.scopes.is_empty() {
        let scopes = &[{{#scopes}}"{{{scope}}}".to_string(),
        {{/scopes}}];
        tok = self.authenticator.token(scopes).await?;
    } else {
        tok = self.authenticator.token(&self.scopes).await?;
    }
    let mut url_params = format!("?{params}", params=params);
    {{#global_params_name}}
    if let Some(ref api_params) = &params.{{{global_params_name}}} {
        url_params.push_str(&format!("{}", api_params));
    }
    {{/global_params_name}}

    let full_uri = path + &url_params;

    let opt_request: Option<EmptyRequest> = None;
    {{#in_type}}
    let opt_request = Some(req);
    {{/in_type}}
    do_request(&self.client, &full_uri,
        &[(hyper::header::AUTHORIZATION, format!("Bearer {token}", token=tok.as_str()))],
        "{{{http_method}}}", opt_request).await
  }
'''

# Takes:
# name, param_type, in_type, out_type
# base_path, rel_path_expr
# params: [{param, snake_param}]
# http_method
UploadMethodTmpl = '''
/// {{{description}}}
///
/// This method is a variant of `{{{name}}}()`, taking data for upload. It performs a multipart upload.
pub async fn {{{name}}}_upload(
    &mut self, params: &{{{param_type}}}, {{#in_type}}req: &{{{in_type}}},{{/in_type}} data: hyper::body::Bytes) -> Result<{{out_type}}> {
    let rel_path = {{{simple_rel_path_expr}}};
    let path = "{{{base_path}}}".to_string() + &rel_path;

    let tok;
    if self.scopes.is_empty() {
        let scopes = &[{{#scopes}}"{{{scope}}}".to_string(),
        {{/scopes}}];
        tok = self.authenticator.token(scopes).await?;
    } else {
        tok = self.authenticator.token(&self.scopes).await?;
    }
    let mut url_params = format!("?uploadType=multipart{params}", params=params);

    {{#global_params_name}}
    if let Some(ref api_params) = &params.{{{global_params_name}}} {
        url_params.push_str(&format!("{}", api_params));
    }
    {{/global_params_name}}

    let full_uri = path + &url_params;
    let opt_request: Option<EmptyRequest> = None;
    {{#in_type}}
    let opt_request = Some(req);
    {{/in_type}}

    do_upload_multipart(&self.client, &full_uri,
        &[(hyper::header::AUTHORIZATION, format!("Bearer {token}", token=tok.as_str()))],
        "{{{http_method}}}", opt_request, data).await
  }
'''

# Takes:
# name, param_type, in_type, out_type
# base_path, rel_path_expr
# params: [{param, snake_param}]
# http_method
ResumableUploadMethodTmpl = '''
/// {{{description}}}
///
/// This method is a variant of `{{{name}}}()`, taking data for upload.
/// It returns a `ResumableUpload` upload manager which you can use to stream larger amounts
/// of data to the API. The result of this call will be returned by the `ResumableUpload` method
/// you choose for the upload.
pub async fn {{{name}}}_resumable_upload<'client>(
    &'client mut self, params: &{{{param_type}}}, {{#in_type}}req: &{{{in_type}}}{{/in_type}}) -> Result<ResumableUpload<'client, {{{out_type}}}>> {

    let rel_path = {{{resumable_rel_path_expr}}};
    let path = "{{{base_path}}}".to_string() + &rel_path;
    let tok;
    if self.scopes.is_empty() {
        let scopes = &[{{#scopes}}"{{{scope}}}".to_string(),
        {{/scopes}}];
        tok = self.authenticator.token(scopes).await?;
    } else {
        tok = self.authenticator.token(&self.scopes).await?;
    }
    let mut url_params = format!("?uploadType=resumable{params}", params=params);
    {{#global_params_name}}
    if let Some(ref api_params) = &params.{{{global_params_name}}} {
        url_params.push_str(&format!("{}", api_params));
    }
    {{/global_params_name}}

    let full_uri = path + &url_params;

    let opt_request: Option<EmptyRequest> = None;
    {{#in_type}}
    let opt_request = Some(req);
    {{/in_type}}
    let (_resp, headers): (EmptyResponse, hyper::HeaderMap) = do_request_with_headers(
        &self.client, &full_uri, &[(hyper::header::AUTHORIZATION, format!("Bearer {token}", token=tok.as_str()))], "{{{http_method}}}", opt_request).await?;
    if let Some(dest) = headers.get(hyper::header::LOCATION) {
        use std::convert::TryFrom;
        Ok(ResumableUpload::new(hyper::Uri::try_from(dest.to_str()?)?, &self.client, 5*1024*1024))
    } else {
        Err(Error::from(ApiError::RedirectError(format!("Resumable upload response didn't contain Location: {:?}", headers)))
        .context(format!("{:?}", headers)))?
    }
  }
'''

# Takes:
# name, param_type, in_type, out_type
# base_path, rel_path_expr
# params: [{param, snake_param}]
# http_method
DownloadMethodTmpl = '''
/// {{{description}}}
///
/// This method downloads data. Depending on the server returning a `Content-Type` of `application/json`
/// or a non-JSON type, the returned value indicates if a download took place or data was written to
/// `dst`. If `dst` is `None` despite data being available for download, `ApiError::DataAvailableError`
/// is returned.
pub async fn {{{name}}}(
    &mut self, params: &{{{param_type}}}, {{#in_type}}req: &{{{in_type}}},{{/in_type}}
    dst: Option<&mut (dyn tokio::io::AsyncWrite + std::marker::Unpin)>)
    -> Result<DownloadResponse<{{out_type}}>> {

    let rel_path = {{{rel_path_expr}}};
    let path = "{{{base_path}}}".to_string() + &rel_path;

    let tok;
    if self.scopes.is_empty() {
        let scopes = &[{{#scopes}}"{{{scope}}}".to_string(),
        {{/scopes}}];
        tok = self.authenticator.token(scopes).await?;
    } else {
        tok = self.authenticator.token(&self.scopes).await?;
    }
    let mut url_params = format!("?{params}", params=params);
    {{#global_params_name}}
    if let Some(ref api_params) = &params.{{{global_params_name}}} {
        url_params.push_str(&format!("{}", api_params));
    }
    {{/global_params_name}}

    let full_uri = path + &url_params;
    let opt_request: Option<EmptyRequest> = None;
    {{#in_type}}
    let opt_request = Some(req);
    {{/in_type}}

    do_download(&self.client, &full_uri, &[(hyper::header::AUTHORIZATION, format!("Bearer {token}", token=tok.as_str()))],
        "{{{http_method}}}", opt_request, dst).await
  }
'''
