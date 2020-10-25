#[derive(Debug)]
pub enum ApiError {
    HTTPResponseError(hyper::StatusCode, String),
    RedirectError(String),
    InputDataError(String),
    DataAvailableError(String),
}

impl std::error::Error for ApiError {}
impl std::fmt::Display for ApiError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        std::fmt::Debug::fmt(self, f)
    }
}
