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

    fn hyper_client() -> agac::TlsClient {
        hyper::Client::builder().build(hyper_rustls::HttpsConnector::new())
    }

    #[tokio::test]
    async fn it_works() {
        mockito::start();
        println!("Mockito running at {}", mockito::server_url());
        let appsec = read_client_secret().await;
        let cl = hyper_client();
        let auth = agac::yup_oauth2::InstalledFlowAuthenticator::builder(
            appsec,
            agac::yup_oauth2::InstalledFlowReturnMethod::Interactive,
        )
        .hyper_client(cl.clone())
        .build();
    }
}
