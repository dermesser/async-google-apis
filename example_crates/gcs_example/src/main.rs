mod storage_v1_types;

use anyhow::Context;
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
    prefix: &str,
) -> common::Result<()> {
    let mut params = storage_v1_types::ObjectsInsertParams::default();
    params.bucket = bucket.into();
    assert!(prefix.ends_with("/") || prefix.is_empty());
    params.name = Some(prefix.to_string() + p.file_name().unwrap().to_str().unwrap());
    let obj = storage_v1_types::Object::default();

    let f = tokio::fs::OpenOptions::new().read(true).open(p).await?;
    let result = cl
        .insert_resumable_upload(&params, &obj)
        .await?
        .set_max_chunksize(1024 * 1024 * 5)?
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
    let mut download = cl.get(&params).await?;

    // Now run the actual download.
    let result = download.do_it(Some(&mut f)).await?;
    match result {
        common::DownloadResult::Downloaded => println!("Downloaded object successfully."),
        common::DownloadResult::Response(_) => panic!("Received response but expected download."),
    }

    Ok(())
}

fn print_objects(objs: &storage_v1_types::Objects) {
    if let Some(ref objs) = objs.items {
        for obj in objs.iter() {
            println!(
                "{} ({} B), class {}. Created @ {} by {}. => {}",
                obj.name.as_ref().unwrap_or(&"(unknown name)".into()),
                obj.size.as_ref().unwrap_or(&"(unknown size)".into()),
                obj.storage_class
                    .as_ref()
                    .unwrap_or(&"(unknown class)".into()),
                obj.time_created
                    .as_ref()
                    .map(|dt| format!("{}", dt))
                    .unwrap_or("(unknown time)".into()),
                obj.owner
                    .as_ref()
                    .unwrap_or(&Default::default())
                    .entity
                    .as_ref()
                    .unwrap_or(&"".into()),
                obj.media_link.as_ref().unwrap_or(&"(unknown link)".into())
            );
        }
    }
}

async fn list_objects(
    mut cl: storage_v1_types::ObjectsService,
    bucket: &str,
    prefix: &str,
) -> common::Result<()> {
    let mut params = storage_v1_types::ObjectsListParams::default();
    params.bucket = bucket.into();
    params.prefix = Some(prefix.into());
    params.storage_params = Some(storage_v1_types::StorageParams::default());
    params.storage_params.as_mut().unwrap().fields = Some("*".into());

    let mut npt = None;
    loop {
        params.page_token = npt.take();
        let result = cl.list(&params).await?;
        print_objects(&result);
        if result.next_page_token.is_some() {
            npt = result.next_page_token.clone();
        } else {
            break;
        }
    }
    Ok(())
}

async fn rm_object(
    mut cl: storage_v1_types::ObjectsService,
    bucket: &str,
    id: &str,
) -> common::Result<()> {
    let mut params = storage_v1_types::ObjectsDeleteParams::default();
    params.bucket = bucket.into();
    params.object = id.into();

    cl.delete(&params).await
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
                .possible_values(&["get", "list", "put", "rm"])
                .required(true)
                .short("a")
                .takes_value(true),
        )
        .arg(
            clap::Arg::with_name("PREFIX")
                .help("When listing with -a list: Prefix of objects to list. When uploading with -a put: Prefix to prepend to filename.")
                .long("prefix")
                .short("p")
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
        .map_err(anyhow::Error::from)
        .context("client_secret.json")
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

    let cl = storage_v1_types::ObjectsService::new(https_client, authenticator);

    if action == "get" {
        let obj = matches
            .value_of("FILE_OR_OBJECT")
            .expect("OBJECT is a mandatory argument.");
        download_file(cl, buck, obj)
            .await
            .expect("Download failed :(");
    } else if action == "put" {
        let fp = matches
            .value_of("FILE_OR_OBJECT")
            .expect("FILE is a mandatory argument.");
        let mut pre = matches.value_of("PREFIX").unwrap_or("").to_string();
        if !pre.ends_with("/") && !pre.is_empty() {
            pre = pre.to_string() + "/";
        }
        upload_file(cl, buck, Path::new(&fp), &pre)
            .await
            .expect("Upload failed :(");
        return;
    } else if action == "list" {
        let prefix = matches.value_of("PREFIX").unwrap_or("");
        list_objects(cl, buck, prefix)
            .await
            .expect("List failed :(");
        return;
    } else if action == "rm" {
        let obj = matches
            .value_of("FILE_OR_OBJECT")
            .expect("OBJECT is a mandatory argument.");
        rm_object(cl, buck, obj).await.expect("rm failed :(");
        return;
    }
}
