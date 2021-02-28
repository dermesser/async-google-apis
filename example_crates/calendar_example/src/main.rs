//! This example lists current google calendars

mod calendar_v3_types;
use calendar_v3_types as gcal;

use env_logger;

use async_google_apis_common as common;

use std::sync::Arc;

/// Create a new HTTPS client.
fn https_client() -> common::TlsClient {
    let conn = hyper_rustls::HttpsConnector::with_native_roots();
    let cl = hyper::Client::builder().build(conn);
    cl
}

async fn gcal_calendars(cl: &gcal::CalendarListService) -> anyhow::Result<gcal::CalendarList> {
    let params = gcal::CalendarListListParams {
        show_deleted: Some(true),
        show_hidden: Some(true),
        ..gcal::CalendarListListParams::default()
    };
    cl.list(&params).await
}

#[tokio::main]
async fn main() {
    env_logger::init();

    let https = https_client();
    // Put your client secret in the working directory!
    let sec = common::yup_oauth2::read_application_secret("client_secret.json")
        .await
        .expect("client secret couldn't be read.");
    let auth = common::yup_oauth2::InstalledFlowAuthenticator::builder(
        sec,
        common::yup_oauth2::InstalledFlowReturnMethod::HTTPRedirect,
    )
    .persist_tokens_to_disk("tokencache.json")
    .hyper_client(https.clone())
    .build()
    .await
    .expect("InstalledFlowAuthenticator failed to build");

    let scopes = vec![
        gcal::CalendarScopes::CalendarReadonly,
        gcal::CalendarScopes::CalendarEventsReadonly,
        gcal::CalendarScopes::Calendar,
        gcal::CalendarScopes::CalendarEvents,
    ];

    let mut cl = gcal::CalendarListService::new(https, Arc::new(auth));
    cl.set_scopes(scopes.clone());

    for cal in gcal_calendars(&cl).await.unwrap().items.unwrap() {
        println!("{:?}", cal);
    }
}
