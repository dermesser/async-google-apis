#[derive(Debug)]
pub enum ApiError {
    /// The API returned a non-OK HTTP response.
    HTTPResponseError(hyper::StatusCode, String),
    /// Returned after being redirected more than five times.
    HTTPTooManyRedirectsError,
    /// E.g. a redirect was issued without a Location: header.
    RedirectError(String),
    /// Invalid data was supplied to the library.
    InputDataError(String),
    /// Data for download is available, but the caller hasn't supplied a destination to write to.
    DataAvailableError(String),
}

impl std::error::Error for ApiError {}
impl std::fmt::Display for ApiError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        std::fmt::Debug::fmt(self, f)
    }
}
