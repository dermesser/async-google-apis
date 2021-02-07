//! Common types, imports, and functions used by generated code, including HTTP requests and error
//! types.
//!
//! This is not very useful on its own -- check out
//! [async-google-apis](https://github.com/dermesser/async-google-apis) on github. It is a code
//! generator, which generates code that utilizes this crate.

mod error;
pub use error::*;
mod http;
pub use http::*;

mod multipart;

pub use hyper;
pub use log::{debug, error, info, trace, warn};
pub use serde;
pub use serde_json;
pub use yup_oauth2;

pub use anyhow::{Error, Result};
pub use chrono::{DateTime, Utc};
pub use percent_encoding::{percent_encode, NON_ALPHANUMERIC};
pub use serde::{de::DeserializeOwned, Deserialize, Serialize};
pub use std::collections::HashMap;
pub use tokio_stream::StreamExt;

pub type Authenticator = yup_oauth2::authenticator::Authenticator<TlsConnr>;
pub type TlsClient = hyper::Client<TlsConnr, hyper::Body>;
pub type TlsConnr = hyper_rustls::HttpsConnector<hyper::client::HttpConnector>;
