// A manual client for a Google API (e.g. Drive), to test what makes sense and what doesn't.

use async_google_apis_common as agac;

mod discovery_v1_types;
mod drive_v3_types;

mod gmail_v1_types;

use discovery_v1_types as disc;
use drive_v3_types as drive;

use yup_oauth2::InstalledFlowAuthenticator;

fn https_client() -> agac::TlsClient {
    let conn = hyper_rustls::HttpsConnector::new();
    let cl = hyper::Client::builder().build(conn);
    cl
}

#[tokio::main]
async fn main() {
    let sec = yup_oauth2::read_application_secret("client_secret.json")
        .await
        .expect("client secret couldn't be read.");

    let mut auth = InstalledFlowAuthenticator::builder(
        sec,
        yup_oauth2::InstalledFlowReturnMethod::HTTPRedirect,
    )
    .persist_tokens_to_disk("tokencache.json")
    .build()
    .await
    .expect("installed flow authenticator!");

    let scopes = &["https://www.googleapis.com/auth/drive.file"];

    let mut cl = https_client();
    let mut disc_svc = disc::ApisService::new(cl);

    let params = disc::ApisListParams::default();
    println!(
        "{}",
        serde_json::to_string_pretty(&disc_svc.list(&params).await.unwrap()).unwrap()
    );

    let mut params = disc::ApisGetRestParams {
        api: "drive".into(),
        version: "v3".into(),
        ..Default::default()
    };
    println!(
        "{}",
        serde_json::to_string_pretty(&disc_svc.get_rest(&params).await.unwrap()).unwrap()
    );
}
