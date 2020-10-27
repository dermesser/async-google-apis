mod integration_test_v1_types;

use async_google_apis_common as agac;
use integration_test_v1_types as inttest;

#[cfg(test)]
mod tests {
    use super::*;
    use mockito;
    use tokio;

    const CLIENT_ID: &str = "myclientid.apps._dev.borgac.net";
    const CLIENT_SECRET: &str = "mysecret";
    const PROJECT_ID: &str = "integration-test-243420";
    const AUTH_PATH: &str = "/oauth2/";
    const TOKEN_PATH: &str = "/token/";

    const API_LOCATION: &str = "/integrationAPI/";

    struct AutoDelegate {}

    impl agac::yup_oauth2::authenticator_delegate::InstalledFlowDelegate for AutoDelegate {
        fn present_user_url<'a>(
            &'a self,
            url: &'a str,
            _need_code: bool,
        ) -> std::pin::Pin<Box<dyn std::future::Future<Output = Result<String, String>> + Send + 'a>>
        {
            println!("user directed to: {}", url);
            return Box::pin(futures::future::ok("returned_code".into()));
        }
    }

    fn url_for_path(path: &str) -> String {
        if path.starts_with("/") {
            return mockito::server_url() + path;
        }
        return mockito::server_url() + "/" + path;
    }

    async fn read_client_secret() -> agac::yup_oauth2::ApplicationSecret {
        let mut appsec = agac::yup_oauth2::read_application_secret("client_secret.json")
            .await
            .unwrap();
        appsec.client_id = CLIENT_ID.into();
        appsec.client_secret = CLIENT_SECRET.into();
        appsec.project_id = Some(PROJECT_ID.into());
        appsec.auth_uri = url_for_path(AUTH_PATH);
        appsec.token_uri = url_for_path(TOKEN_PATH);
        appsec.auth_provider_x509_cert_url = None;
        appsec
    }

    async fn authenticator(
        cl: agac::TlsClient,
    ) -> agac::yup_oauth2::authenticator::Authenticator<agac::TlsConnr> {
        let appsec = read_client_secret().await;
        let auth = agac::yup_oauth2::InstalledFlowAuthenticator::builder(
            appsec,
            agac::yup_oauth2::InstalledFlowReturnMethod::Interactive,
        )
        .flow_delegate(Box::new(AutoDelegate {}))
        .hyper_client(cl)
        .build()
        .await
        .unwrap();
        auth
    }

    fn oauth_mock() -> mockito::Mock {
        mockito::mock("POST", "/token/")
                .with_status(200)
                .match_header("content-type", "application/x-www-form-urlencoded")
                .match_body("code=returned_code&client_id=myclientid.apps._dev.borgac.net&client_secret=mysecret&redirect_uri=urn%3Aietf%3Awg%3Aoauth%3A2.0%3Aoob&grant_type=authorization_code")
                .with_body(r#" { "access_token": "returned_access_token!", "refresh_token": "returned_refresh_token!", "token_type": "bearer" } "#)
                .create()
    }

    fn hyper_client() -> agac::TlsClient {
        hyper::Client::builder().build(hyper_rustls::HttpsConnector::new())
    }

    fn files_service(
        cl: agac::TlsClient,
        auth: agac::yup_oauth2::authenticator::Authenticator<agac::TlsConnr>,
    ) -> inttest::FilesService {
        let mut fs = inttest::FilesService::new(cl, Box::new(auth));
        fs.set_urls(mockito::server_url() + API_LOCATION, mockito::server_url());
        fs
    }

    #[tokio::test]
    async fn it_works() {
        mockito::start();
        println!("Mockito running at {}", mockito::server_url());
    }

    #[tokio::test]
    async fn test_oauth_provider() {
        mockito::start();
        let cl = hyper_client();
        let auth = authenticator(cl.clone()).await;

        let mock = oauth_mock();
        let tok = auth
            .token(&["https://oauth.borgac.net/test"])
            .await
            .unwrap();
        println!("Obtained token: {:?}", tok);
        mock.assert();
    }

    #[tokio::test]
    async fn test_basic_files_api() {
        mockito::start();
        let cl = hyper_client();
        let auth = authenticator(cl.clone()).await;
        let mut svc = files_service(cl, auth);

        // Mandatory for token fetching.
        let _om = oauth_mock();

        let mock = mockito::mock("PUT", "/integrationAPI/files/file_id_to_copy/copy").with_status(200).create();

        let mut fsp = inttest::FilesCopyParams::default();
        fsp.file_id = "file_id_to_copy".into();
        let f = inttest::File::default();
        let result = svc.copy(&fsp, &f).await.unwrap();

        mock.assert();
    }
}
