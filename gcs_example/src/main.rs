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
    params.name = Some(p.file_name().unwrap().to_str().unwrap().into());
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

async fn download_file(
    mut cl: storage_v1_types::ObjectsService,
    bucket: &str,
    id: &str,
) -> common::Result<()> {
    // Set alt=media for download.
    let mut gparams = storage_v1_types::StorageParams::default();
    gparams.alt = Some("media".into());
    let mut params = storage_v1_types::ObjectsGetParams::default();
    params.storage_params = Some(gparams);
    params.bucket = bucket.into();
    params.object = id.into();

    let id = id.replace("/", "_");
    let mut f = tokio::fs::OpenOptions::new()
        .write(true)
        .create(true)
        .open(id)
        .await?;
    let result = cl.get(&params, Some(&mut f)).await?;

    println!("Downloaded object: {:?}", result);

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
                .help("target bucket")
                .long("bucket")
                .required(true)
                .short("b")
                .takes_value(true),
        )
        .arg(
            clap::Arg::with_name("ACTION")
                .help("What to do.")
                .long("action")
                .possible_values(&["get", "list", "put"])
                .required(true)
                .short("a")
                .takes_value(true),
        )
        .arg(
            clap::Arg::with_name("FILE_OR_OBJECT")
                .help("File to upload")
                .index(1),
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
    let authenticator = std::rc::Rc::new(authenticator);

    let action = matches.value_of("ACTION").expect("--action is required.");
    let buck = matches
        .value_of("BUCKET")
        .expect("--bucket is a mandatory argument.");

    if action == "get" {
        let obj = matches
            .value_of("FILE_OR_OBJECT")
            .expect("OBJECT is a mandatory argument.");
        let cl = storage_v1_types::ObjectsService::new(https_client, authenticator);
        download_file(cl, buck, obj)
            .await
            .expect("Download failed :(");
    } else if action == "put" {
        let fp = matches
            .value_of("FILE_OR_OBJECT")
            .expect("FILE is a mandatory argument.");
        let cl = storage_v1_types::ObjectsService::new(https_client, authenticator);
        upload_file(cl, buck, Path::new(&fp))
            .await
            .expect("Upload failed :(");
        return;
    }
}
