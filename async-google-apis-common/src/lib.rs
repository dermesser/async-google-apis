//! Common types, imports, and functions used by generated code, including HTTP requests and error
//! types.

pub use hyper;
pub use serde;
pub use serde_json;
pub use yup_oauth2;

pub use anyhow::{Error, Result};
pub use chrono::{DateTime, Utc};
pub use percent_encoding::{percent_encode, NON_ALPHANUMERIC};
pub use serde::{de::DeserializeOwned, Deserialize, Serialize};
pub use std::collections::HashMap;
pub use tokio::stream::StreamExt;

pub type Authenticator = yup_oauth2::authenticator::Authenticator<TlsConnr>;
pub type TlsClient = hyper::Client<TlsConnr, hyper::Body>;
pub type TlsConnr = hyper_rustls::HttpsConnector<hyper::client::HttpConnector>;

#[derive(Debug, Clone)]
pub enum ApiError {
    InputDataError(String),
    HTTPError(hyper::StatusCode, String),
}

impl std::error::Error for ApiError {}
impl std::fmt::Display for ApiError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        std::fmt::Debug::fmt(self, f)
    }
}

/// This type is used as type parameter to the following functions, when `rq` is `None`.
#[derive(Serialize)]
pub struct EmptyRequest {}

/// The Content-Type header is set automatically to application/json.
pub async fn do_request<Req: Serialize, Resp: DeserializeOwned + Clone>(
    cl: &TlsClient,
    path: &str,
    headers: &[(String, String)],
    http_method: &str,
    rq: Option<Req>,
) -> Result<Resp> {
    let mut reqb = hyper::Request::builder().uri(path).method(http_method);
    for (k, v) in headers {
        reqb = reqb.header(k, v);
    }
    reqb = reqb.header("Content-Type", "application/json");
    let body_str;
    if let Some(rq) = rq {
        body_str = serde_json::to_string(&rq)?;
    } else {
        body_str = "".to_string();
    }

    let body;
    if body_str == "null" {
        body = hyper::Body::from("");
    } else {
        body = hyper::Body::from(body_str);
    }

    let http_request = reqb.body(body)?;
    let http_response = cl.request(http_request).await?;
    let status = http_response.status();
    let response_body = hyper::body::to_bytes(http_response.into_body()).await?;
    let response_body_str = String::from_utf8(response_body.to_vec());
    if !status.is_success() {
        Err(Error::new(ApiError::HTTPError(
            status,
            response_body_str.unwrap_or("".to_string()),
        )))
    } else {
        serde_json::from_reader(response_body.as_ref()).map_err(Error::from)
    }
}

/// The Content-Length header is set automatically.
pub async fn do_upload<Resp: DeserializeOwned + Clone>(
    cl: &TlsClient,
    path: &str,
    headers: &[(String, String)],
    http_method: &str,
    data: hyper::body::Bytes,
) -> Result<Resp> {
    let mut reqb = hyper::Request::builder().uri(path).method(http_method);
    for (k, v) in headers {
        reqb = reqb.header(k, v);
    }
    reqb = reqb.header("Content-Length", data.len());

    let body = hyper::Body::from(data);
    let http_request = reqb.body(body)?;
    let http_response = cl.request(http_request).await?;
    let status = http_response.status();
    let response_body = hyper::body::to_bytes(http_response.into_body()).await?;
    let response_body_str = String::from_utf8(response_body.to_vec());

    if !status.is_success() {
        Err(Error::new(ApiError::HTTPError(
            status,
            response_body_str.unwrap_or("".to_string()),
        )))
    } else {
        serde_json::from_reader(response_body.as_ref()).map_err(Error::from)
    }
}

pub async fn do_download<Req: Serialize>(
    cl: &TlsClient,
    path: &str,
    headers: &[(String, String)],
    http_method: &str,
    rq: Option<Req>,
    dst: &mut dyn std::io::Write,
) -> Result<()> {
    let mut path = path.to_string();
    let mut http_response;

    // Follow redirects.
    loop {
        let mut reqb = hyper::Request::builder().uri(&path).method(http_method);
        for (k, v) in headers {
            reqb = reqb.header(k, v);
        }
        let body_str = serde_json::to_string(&rq)?;
        let body;
        if body_str == "null" {
            body = hyper::Body::from("");
        } else {
            body = hyper::Body::from(body_str);
        }

        let http_request = reqb.body(body)?;
        http_response = Some(cl.request(http_request).await?);
        let status = http_response.as_ref().unwrap().status();

        if status.is_success() {
            break;
        } else if status.is_redirection() {
            let new_location = http_response
                .as_ref()
                .unwrap()
                .headers()
                .get(hyper::header::LOCATION);
            if new_location.is_none() {
                return Err(Error::new(ApiError::HTTPError(
                    status,
                    format!("Redirect doesn't contain a Location: header"),
                )));
            }
            path = new_location.unwrap().to_str()?.to_string();
            continue;
        } else if !status.is_success() {
            return Err(Error::new(ApiError::HTTPError(status, String::new())));
        }
    }

    let response_body = http_response.unwrap().into_body();
    let write_results = response_body
        .map(move |chunk| dst.write(chunk?.as_ref()).map(|_| ()).map_err(Error::from))
        .collect::<Vec<Result<()>>>()
        .await;
    if let Some(e) = write_results.into_iter().find(|r| r.is_err()) {
        return e;
    }
    Ok(())
}
