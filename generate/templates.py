# General imports and error type.
RustHeader = '''
use serde::{Deserialize, Serialize};
use chrono::{DateTime, Utc};
use anyhow::{Error, Result};
use std::collections::HashMap;
use percent_encoding::{percent_encode, NON_ALPHANUMERIC};

pub type TlsConnr = hyper_rustls::HttpsConnector<hyper::client::HttpConnector>;
pub type TlsClient = hyper::Client<TlsConnr, hyper::Body>;
pub type Authenticator = yup_oauth2::authenticator::Authenticator<TlsConnr>;

#[derive(Debug, Clone)]
pub enum ApiError {
  InputDataError(String),
  HTTPError(hyper::StatusCode),
}

impl std::error::Error for ApiError {}
impl std::fmt::Display for ApiError {
  fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
    std::fmt::Debug::fmt(self, f)
  }
}
'''

# A struct for parameters or input/output API types.
ResourceStructTmpl = '''
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

# Dict contents --
# service (e.g. Files)
# [methods] ([{'text': ...}])
ServiceImplementationTmpl = '''
pub struct {{{service}}}Service {
  client: TlsClient,
  authenticator: Authenticator,
  scopes: Vec<String>,
}

impl {{{service}}}Service {
  /// Create a new {{service}}Service object.
  pub fn new(client: TlsClient, auth: Authenticator) -> {{service}}Service {
    {{{service}}}Service { client: client, authenticator: auth, scopes: vec![] }
  }

  /// Explicitly select which scopes should be requested for authorization. Otherwise,
  /// a possibly too large scope will be requested.
  pub fn set_scopes<S: AsRef<str>, T: AsRef<[S]>>(&mut self, scopes: T) {
    self.scopes = scopes.as_ref().into_iter().map(|s| s.as_ref().to_string()).collect();
  }

  {{#methods}}
  {{{text}}}
  {{/methods}}

}
'''

# Takes:
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
    let mut scopes = &self.scopes;
    if scopes.is_empty() {
        scopes = &vec![{{#scopes}}"{{{scope}}}".to_string(),
        {{/scopes}}];
    }
    let tok = self.authenticator.token(&self.scopes).await?;
    let mut url_params = format!("?oauth_token={token}&fields=*", token=tok.as_str());
    {{#params}}
    if let Some(ref val) = &params.{{{snake_param}}} {
        url_params.push_str(&format!("&{{{param}}}={}",
            percent_encode(format!("{}", val).as_bytes(), NON_ALPHANUMERIC).to_string()));
    }
    {{/params}}
    {{#required_params}}
    url_params.push_str(&format!("&{{{param}}}={}",
        percent_encode(format!("{}", params.{{{snake_param}}}).as_bytes(), NON_ALPHANUMERIC).to_string()));
    {{/required_params}}

    let full_uri = path + &url_params;
    let reqb = hyper::Request::builder()
        .uri(full_uri)
        .method("{{{http_method}}}")
        .header("Content-Type", "application/json");

    let body = hyper::Body::from("");
    {{#in_type}}
    let mut body_str = serde_json::to_string(req)?;
    if body_str == "null" {
        body_str.clear();
    }
    let body = hyper::Body::from(body_str);
    {{/in_type}}
    let request = reqb.body(body)?;
    let resp = self.client.request(request).await?;
    if !resp.status().is_success() {
        return Err(anyhow::Error::new(ApiError::HTTPError(resp.status())));
    }
    let resp_body = hyper::body::to_bytes(resp.into_body()).await?;
    let bodystr = String::from_utf8(resp_body.to_vec())?;
    let decoded = serde_json::from_str(&bodystr)?;
    Ok(decoded)
  }
'''

# Takes:
# name, param_type, in_type, out_type
# base_path, rel_path_expr
# params: [{param, snake_param}]
# http_method
UploadMethodTmpl = '''
/// {{{description}}}
pub async fn {{{name}}}_upload(
    &mut self, params: &{{{param_type}}}, data: hyper::body::Bytes) -> Result<{{out_type}}> {
    let rel_path = {{{rel_path_expr}}};
    let path = "{{{base_path}}}".to_string() + &rel_path;
    let tok = self.authenticator.token(&self.scopes).await?;
    let mut url_params = format!("?uploadType=media&oauth_token={token}&fields=*", token=tok.as_str());

    {{#params}}
    if let Some(ref val) = &params.{{{snake_param}}} {
        url_params.push_str(&format!("&{{{param}}}={}",
            percent_encode(format!("{}", val).as_bytes(), NON_ALPHANUMERIC).to_string()));
    }
    {{/params}}
    {{#required_params}}
    url_params.push_str(&format!("&{{{param}}}={}",
        percent_encode(format!("{}", params.{{{snake_param}}}).as_bytes(), NON_ALPHANUMERIC).to_string()));
    {{/required_params}}

    let full_uri = path + &url_params;
    let reqb = hyper::Request::builder()
        .uri(full_uri)
        .method("{{{http_method}}}")
        .header("Content-Length", data.len());
    let body = hyper::Body::from(data);
    let request = reqb.body(body)?;
    let resp = self.client.request(request).await?;
    if !resp.status().is_success() {
        return Err(anyhow::Error::new(ApiError::HTTPError(resp.status())));
    }
    let resp_body = hyper::body::to_bytes(resp.into_body()).await?;
    let bodystr = String::from_utf8(resp_body.to_vec())?;
    let decoded = serde_json::from_str(&bodystr)?;
    Ok(decoded)
  }
'''
