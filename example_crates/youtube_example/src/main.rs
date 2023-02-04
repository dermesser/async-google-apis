//! List most famous Youtube videos.
//!
//! When run with no arguments, the top 5 videos id, title and duration will be shown
//!
mod youtube_v3_types;
use youtube_v3_types as yt;

use env_logger;

use async_google_apis_common as common;

use std::sync::Arc;

/// Create a new HTTPS client.
fn https_client() -> common::TlsClient {
    let conn = hyper_rustls::HttpsConnectorBuilder::new().with_native_roots().https_or_http().enable_http2().build();
    let cl = hyper::Client::builder().build(conn);
    cl
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
        yt::YoutubeScopes::YoutubeUpload,
        yt::YoutubeScopes::YoutubeForceSsl,
    ];
    let mut cl = yt::VideosService::new(https, Arc::new(auth));
    cl.set_scopes(&scopes);

    {
        // By default, list most popular videos
        let mut general_params = yt::YoutubeParams::default();
        general_params.fields = Some("*".to_string());
        let mut p = yt::VideosListParams::default();
        p.youtube_params = Some(general_params);
        p.part = "id,contentDetails,snippet".into();
        p.chart = Some(yt::VideosListChart::MostPopular);

        let resp = cl.list(&p).await.expect("listing your yt failed!");
        if let Some(videos) = resp.items {
            for f in videos {
                println!(
                    "{} => duration: {} title: '{}'",
                    f.id.unwrap(),
                    f.content_details
                        .map(|cd| cd.duration.unwrap_or("n.a.".to_string()))
                        .unwrap(),
                    f.snippet
                        .map(|s| s.title.unwrap_or("n.a.".to_string()))
                        .unwrap()
                );
            }
        }
    }
}
