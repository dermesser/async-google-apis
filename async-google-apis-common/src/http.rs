use crate::*;

use anyhow::Context;

fn body_to_str(b: hyper::body::Bytes) -> String {
    String::from_utf8(b.to_vec()).unwrap_or("[UTF-8 decode failed]".into())
}

/// This type is used as type parameter to the following functions, when `rq` is `None`.
#[derive(Debug, Serialize)]
pub struct EmptyRequest {}

/// This type is used as type parameter for when no response is expected.
#[derive(Debug, Deserialize, Clone, Default)]
pub struct EmptyResponse {}

/// The Content-Type header is set automatically to application/json.
pub async fn do_request<
    Req: Serialize + std::fmt::Debug,
    Resp: DeserializeOwned + Clone + Default,
>(
    cl: &TlsClient,
    path: &str,
    headers: &[(hyper::header::HeaderName, String)],
    http_method: &str,
    rq: Option<Req>,
) -> Result<Resp> {
    use futures::future::FutureExt;
    do_request_with_headers(cl, path, headers, http_method, rq)
        .map(|r| r.map(|t| t.0))
        .await
}

/// The Content-Type header is set automatically to application/json. Also returns response
/// headers.
pub async fn do_request_with_headers<
    Req: Serialize + std::fmt::Debug,
    Resp: DeserializeOwned + Clone + Default,
>(
    cl: &TlsClient,
    path: &str,
    headers: &[(hyper::header::HeaderName, String)],
    http_method: &str,
    rq: Option<Req>,
) -> Result<(Resp, hyper::HeaderMap)> {
    let mut reqb = hyper::Request::builder().uri(path).method(http_method);
    for (k, v) in headers {
        reqb = reqb.header(k, v);
    }
    reqb = reqb.header("Content-Type", "application/json");
    let body_str;
    if let Some(rq) = rq {
        body_str = serde_json::to_string(&rq).context(format!("{:?}", rq))?;
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

    debug!("do_request: Launching HTTP request: {:?}", http_request);

    let http_response = cl.request(http_request).await?;
    let status = http_response.status();

    debug!(
        "do_request: HTTP response with status {} received: {:?}",
        status, http_response
    );

    let headers = http_response.headers().clone();
    let response_body = hyper::body::to_bytes(http_response.into_body()).await?;
    if !status.is_success() {
        Err(ApiError::HTTPResponseError(status, body_to_str(response_body)).into())
    } else {
        // Evaluate body_to_str lazily
        if response_body.len() > 0 {
            serde_json::from_reader(response_body.as_ref())
                .map_err(|e| anyhow::Error::from(e).context(body_to_str(response_body)))
                .map(|r| (r, headers))
        } else {
            Ok((Default::default(), headers))
        }
    }
}

/// The Content-Length header is set automatically.
pub async fn do_upload_multipart<
    Req: Serialize + std::fmt::Debug,
    Resp: DeserializeOwned + Clone,
>(
    cl: &TlsClient,
    path: &str,
    headers: &[(hyper::header::HeaderName, String)],
    http_method: &str,
    req: Option<Req>,
    data: hyper::body::Bytes,
) -> Result<Resp> {
    let mut reqb = hyper::Request::builder().uri(path).method(http_method);
    for (k, v) in headers {
        reqb = reqb.header(k, v);
    }

    let data = multipart::format_multipart(&req, data)?;
    reqb = reqb.header("Content-Length", data.as_ref().len());
    reqb = reqb.header(
        "Content-Type",
        format!("multipart/related; boundary={}", multipart::MIME_BOUNDARY),
    );

    let body = hyper::Body::from(data.as_ref().to_vec());
    let http_request = reqb.body(body)?;
    debug!(
        "do_upload_multipart: Launching HTTP request: {:?}",
        http_request
    );
    let http_response = cl.request(http_request).await?;
    let status = http_response.status();
    debug!(
        "do_upload_multipart: HTTP response with status {} received: {:?}",
        status, http_response
    );
    let response_body = hyper::body::to_bytes(http_response.into_body()).await?;

    if !status.is_success() {
        Err(ApiError::HTTPResponseError(status, body_to_str(response_body)).into())
    } else {
        serde_json::from_reader(response_body.as_ref())
            .map_err(|e| anyhow::Error::from(e).context(body_to_str(response_body)))
    }
}

pub async fn do_download<Req: Serialize + std::fmt::Debug>(
    cl: &TlsClient,
    path: &str,
    headers: &[(hyper::header::HeaderName, String)],
    http_method: &str,
    rq: Option<Req>,
    dst: &mut dyn std::io::Write,
) -> Result<()> {
    let mut path = path.to_string();
    let mut http_response;
    let mut i = 0;

    // Follow redirects.
    loop {
        let mut reqb = hyper::Request::builder().uri(&path).method(http_method);
        for (k, v) in headers {
            reqb = reqb.header(k, v);
        }
        let body_str = serde_json::to_string(&rq).context(format!("{:?}", rq))?;
        let body;
        if body_str == "null" {
            body = hyper::Body::from("");
        } else {
            body = hyper::Body::from(body_str);
        }

        let http_request = reqb.body(body)?;
        debug!(
            "do_download: Redirect {}, Launching HTTP request: {:?}",
            i, http_request
        );

        http_response = Some(cl.request(http_request).await?);
        let status = http_response.as_ref().unwrap().status();
        debug!(
            "do_download: Redirect {}, HTTP response with status {} received: {:?}",
            i, status, http_response
        );

        if status.is_success() {
            break;
        } else if status.is_redirection() {
            i += 1;
            let new_location = http_response
                .as_ref()
                .unwrap()
                .headers()
                .get(hyper::header::LOCATION);
            if new_location.is_none() {
                return Err(ApiError::RedirectError(format!(
                    "Redirect doesn't contain a Location: header"
                ))
                .into());
            }
            path = new_location.unwrap().to_str()?.to_string();
            continue;
        } else if !status.is_success() {
            return Err(ApiError::HTTPResponseError(
                status,
                body_to_str(hyper::body::to_bytes(http_response.unwrap().into_body()).await?),
            )
            .into());
        }
    }

    let response_body = http_response.unwrap().into_body();
    let write_results = response_body
        .map(move |chunk| {
            dst.write(chunk?.as_ref())
                .map(|_| ())
                .map_err(anyhow::Error::from)
        })
        .collect::<Vec<Result<()>>>()
        .await;
    if let Some(e) = write_results.into_iter().find(|r| r.is_err()) {
        return e;
    }
    Ok(())
}

/// A resumable upload in progress, useful for sending large objects.
pub struct ResumableUpload<'client, Response: DeserializeOwned> {
    dest: hyper::Uri,
    cl: &'client TlsClient,
    max_chunksize: usize,
    _resp: std::marker::PhantomData<Response>,
}

fn format_content_range(from: usize, to: usize, total: usize) -> String {
    format!("bytes {}-{}/{}", from, to, total)
}

fn parse_response_range(rng: &str) -> Option<(usize, usize)> {
    if let Some(main) = rng.strip_prefix("bytes=") {
        let mut parts = main.split("-");
        let (first, second) = (parts.next(), parts.next());
        if first.is_none() || second.is_none() {
            return None;
        }
        Some((
            usize::from_str_radix(first.unwrap(), 10).unwrap_or(0),
            usize::from_str_radix(second.unwrap(), 10).unwrap_or(0),
        ))
    } else {
        None
    }
}

impl<'client, Response: DeserializeOwned> ResumableUpload<'client, Response> {
    pub fn new(
        to: hyper::Uri,
        cl: &'client TlsClient,
        max_chunksize: usize,
    ) -> ResumableUpload<'client, Response> {
        ResumableUpload {
            dest: to,
            cl: cl,
            max_chunksize: max_chunksize,
            _resp: Default::default(),
        }
    }
    pub fn set_max_chunksize(&mut self, size: usize) {
        self.max_chunksize = size;
    }

    /// Upload data from a reader; use only if the reader cannot be seeked. Memory usage is higher,
    /// because data needs to be cached if the server hasn't accepted all data.
    pub async fn upload<R: tokio::io::AsyncRead + std::marker::Unpin>(
        &self,
        mut f: R,
        size: usize,
    ) -> Result<Response> {
        use tokio::io::AsyncReadExt;

        // Cursor to current position in stream.
        let mut current = 0;
        // Buffer portion that we couldn't send previously.
        let mut previously_unsent = None;
        loop {
            let chunksize = if (size - current) > self.max_chunksize {
                self.max_chunksize
            } else {
                size - current
            };

            let mut buf: Vec<u8>;
            let read_from_stream;
            if let Some(buf2) = previously_unsent.take() {
                buf = buf2;
                read_from_stream = buf.len();
            } else {
                buf = vec![0 as u8; chunksize];
                // Move buffer into body.
                read_from_stream = f.read_exact(&mut buf).await?;
                buf.resize(read_from_stream, 0);
            }

            let reqb = hyper::Request::builder()
                .uri(self.dest.clone())
                .method(hyper::Method::PUT)
                .header(hyper::header::CONTENT_LENGTH, read_from_stream)
                .header(
                    hyper::header::CONTENT_RANGE,
                    format_content_range(current, current + read_from_stream - 1, size),
                )
                .header(hyper::header::CONTENT_TYPE, "application/octet-stream");
            let request = reqb.body(hyper::Body::from(buf[..].to_vec()))?;
            debug!("upload_file: Launching HTTP request: {:?}", request);

            let response = self.cl.request(request).await?;
            debug!("upload_file: Received response: {:?}", response);

            let status = response.status();
            // 308 means: continue upload.
            if !status.is_success() && status.as_u16() != 308 {
                debug!("upload_file: Encountered error: {}", status);
                return Err(ApiError::HTTPResponseError(status, status.to_string())).context(
                    body_to_str(hyper::body::to_bytes(response.into_body()).await?),
                );
            }

            let sent;
            if let Some(rng) = response.headers().get(hyper::header::RANGE) {
                if let Some((_, to)) = parse_response_range(rng.to_str()?) {
                    sent = to + 1 - current;
                    if sent < read_from_stream {
                        previously_unsent = Some(buf.split_off(sent));
                    }
                    current = to + 1;
                } else {
                    sent = read_from_stream;
                    current += read_from_stream;
                }
            } else {
                sent = read_from_stream;
                current += read_from_stream;
            }

            debug!(
                "upload_file: Sent {} bytes (successful: {}) of total {} to {}",
                chunksize, sent, size, self.dest
            );

            if current >= size {
                let headers = response.headers().clone();
                let response_body = hyper::body::to_bytes(response.into_body()).await?;

                if !status.is_success() {
                    return Err(Error::from(ApiError::HTTPResponseError(
                        status,
                        body_to_str(response_body),
                    ))
                    .context(format!("{:?}", headers)));
                } else {
                    return serde_json::from_reader(response_body.as_ref()).map_err(|e| {
                        anyhow::Error::from(e)
                            .context(body_to_str(response_body))
                            .context(format!("{:?}", headers))
                    });
                }
            }
        }
    }
    /// Upload content from a file. This is most efficient if you have an actual file, as seek can
    /// be used in case the server didn't accept all data.
    pub async fn upload_file(&self, mut f: tokio::fs::File) -> Result<Response> {
        use tokio::io::AsyncReadExt;

        let len = f.metadata().await?.len() as usize;
        let mut current = 0;
        loop {
            let chunksize = if (len - current) > self.max_chunksize {
                self.max_chunksize
            } else {
                len - current
            };

            f.seek(std::io::SeekFrom::Start(current as u64)).await?;

            let mut buf = vec![0 as u8; chunksize];
            // Move buffer into body.
            let read_from_stream = f.read_exact(&mut buf).await?;
            buf.resize(read_from_stream, 0);

            let reqb = hyper::Request::builder()
                .uri(self.dest.clone())
                .method(hyper::Method::PUT)
                .header(hyper::header::CONTENT_LENGTH, read_from_stream)
                .header(
                    hyper::header::CONTENT_RANGE,
                    format_content_range(current, current + read_from_stream - 1, len),
                )
                .header(hyper::header::CONTENT_TYPE, "application/octet-stream");
            let request = reqb.body(hyper::Body::from(buf))?;
            debug!("upload_file: Launching HTTP request: {:?}", request);

            let response = self.cl.request(request).await?;
            debug!("upload_file: Received response: {:?}", response);

            let status = response.status();
            // 308 means: continue upload.
            if !status.is_success() && status.as_u16() != 308 {
                debug!("upload_file: Encountered error: {}", status);
                return Err(ApiError::HTTPResponseError(status, status.to_string())).context(
                    body_to_str(hyper::body::to_bytes(response.into_body()).await?),
                );
            }

            let sent;
            if let Some(rng) = response.headers().get(hyper::header::RANGE) {
                if let Some((_, to)) = parse_response_range(rng.to_str()?) {
                    sent = to + 1 - current;
                    current = to + 1;
                } else {
                    sent = read_from_stream;
                    current += read_from_stream;
                }
            } else {
                // This can also happen if response code is 200.
                sent = read_from_stream;
                current += read_from_stream;
            }

            debug!(
                "upload_file: Sent {} bytes (successful: {}) of total {} to {}",
                chunksize, sent, len, self.dest
            );

            if current >= len {
                let headers = response.headers().clone();
                let response_body = hyper::body::to_bytes(response.into_body()).await?;

                if !status.is_success() {
                    return Err(Error::from(ApiError::HTTPResponseError(
                        status,
                        body_to_str(response_body),
                    ))
                    .context(format!("{:?}", headers)));
                } else {
                    return serde_json::from_reader(response_body.as_ref()).map_err(|e| {
                        anyhow::Error::from(e)
                            .context(body_to_str(response_body))
                            .context(format!("{:?}", headers))
                    });
                }
            }
        }
    }
}
