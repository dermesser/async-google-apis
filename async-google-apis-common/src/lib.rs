
pub use hyper;
pub use serde;
pub use serde_json;
pub use yup_oauth2;

pub use anyhow::{Error, Result};
pub use chrono::{DateTime, Utc};
pub use percent_encoding::{percent_encode, NON_ALPHANUMERIC};
pub use serde::{Deserialize, Serialize};
pub use std::collections::HashMap;
pub use tokio::stream::StreamExt;

pub type Authenticator = yup_oauth2::authenticator::Authenticator<TlsConnr>;
pub type TlsClient = hyper::Client<TlsConnr, hyper::Body>;
pub type TlsConnr = hyper_rustls::HttpsConnector<hyper::client::HttpConnector>;

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

