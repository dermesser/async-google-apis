mod storage_v1_types;

use async_google_apis_common as common;

use env_logger;

use std::path::Path;

/// Create a new HTTPS client.
fn https_client() -> common::TlsClient {
    let conn = hyper_rustls::HttpsConnector::new();
    let cl = hyper::Client::builder().build(conn);
    cl
}

async fn upload_file(
    mut cl: storage_v1_types::ObjectsService,
    bucket: &str,
    p: &Path,
) -> common::Result<()> {
    let mut params = storage_v1_types::ObjectsInsertParams::default();
    params.bucket = bucket.into();
    params.name = Some("test_directory/".to_string() + p.file_name().unwrap().to_str().unwrap());
    let obj = storage_v1_types::Object::default();

    let f = tokio::fs::OpenOptions::new().read(true).open(p).await?;
    let result = cl
        .insert_resumable_upload(&params, &obj)
        .await?
        .set_max_chunksize(1024 * 1024)?
        .upload_file(f)
        .await?;

    println!("Uploaded object: {:?}", result);

    Ok(())
}

#[tokio::main]
async fn main() {
    env_logger::init();

    let matches = clap::App::new("gcs_example")
        .version("0.1")
        .about("Upload objects to GCS.")
        .arg(
            clap::Arg::with_name("BUCKET")
                .long("bucket")
                .help("target bucket")
                .takes_value(true),
        )
        .arg(
            clap::Arg::with_name("FILE")
                .help("File to upload")
                .required(true)
                .index(1)
                .takes_value(true),
        )
        .get_matches();

    let https_client = https_client();
    let service_account_key = common::yup_oauth2::read_service_account_key("client_secret.json")
        .await
        .unwrap();
    let authenticator =
        common::yup_oauth2::ServiceAccountAuthenticator::builder(service_account_key)
            .hyper_client(https_client.clone())
            .persist_tokens_to_disk("tokencache.json")
            .build()
            .await
            .expect("ServiceAccount authenticator failed.");

    let cl = storage_v1_types::ObjectsService::new(https_client, std::rc::Rc::new(authenticator));

    if let Some(fp) = matches.value_of("FILE") {
        if let Some(buck) = matches.value_of("BUCKET") {
            upload_file(cl, buck, Path::new(&fp))
                .await
                .expect("Upload failed :(");
            return;
        }
    }
    println!("Please specify file to upload as first argument.");
}
