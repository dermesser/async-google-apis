//! List your Google Drive root folder, or upload a file there.
//!
//! When run with no arguments, a very detailed listing of all objects in your root folder is
//! printed.
//!
//! When you specify a file name as command line argument, the given file is uploaded to your
//! Google Drive.

mod drive_v3_types;
use drive_v3_types as drive;

use std::fs;
use std::path::Path;

/// Create a new HTTPS client.
fn https_client() -> drive::TlsClient {
    let conn = hyper_rustls::HttpsConnector::new();
    let cl = hyper::Client::builder().build(conn);
    cl
}

/// Upload a local file `f` to your drive.
async fn upload_file(mut cl: drive::FilesService, f: &Path) -> anyhow::Result<()> {
    cl.set_scopes(&["https://www.googleapis.com/auth/drive.file"]);

    let data = hyper::body::Bytes::from(fs::read(&f)?);
    let mut params = drive::FilesCreateParams::default();
    params.include_permissions_for_view = Some("published".to_string());
    println!("{:?}", params);

    // Upload data using the upload version of create(). We obtain a `File` object.
    let resp = cl.create_upload(&params, data).await?;
    println!("{:?}", resp);

    // Copy ID from response.
    let file_id = resp.id.unwrap();
    let fname = f.file_name().unwrap().to_str().unwrap();

    // Rename file to the file name on our computer.
    let mut params = drive::FilesUpdateParams::default();
    println!("{:?}", params);

    params.file_id = file_id.clone();
    params.include_permissions_for_view = Some("published".to_string());
    let mut file = drive::File::default();
    file.name = Some(fname.to_string());

    let update_resp = cl.update(&params, &file).await;
    println!("{:?}", update_resp);

    // Now get the file and check that it is correct.
    let mut params = drive::FilesGetParams::default();
    params.file_id = file_id.clone();

    let get_file = cl.get(&params).await?;
    println!("{:?}", get_file);

    assert!(get_file.name == Some(fname.to_string()));
    Ok(())
}

#[tokio::main]
async fn main() {
    // Put your client secret in the working directory!
    let sec = yup_oauth2::read_application_secret("client_secret.json")
        .await
        .expect("client secret couldn't be read.");
    let auth = yup_oauth2::InstalledFlowAuthenticator::builder(
        sec,
        yup_oauth2::InstalledFlowReturnMethod::HTTPRedirect,
    )
    .persist_tokens_to_disk("tokencache.json")
    .build()
    .await
    .expect("InstalledFlowAuthenticator failed to build");

    let scopes = &["https://www.googleapis.com/auth/drive"];
    let https = https_client();
    let mut cl = drive::FilesService::new(https, auth);
    cl.set_scopes(scopes);

    let arg = std::env::args().skip(1).next();
    if let Some(fp) = arg {
        upload_file(cl, Path::new(&fp))
            .await
            .expect("Upload failed :(");
    } else {
        // By default, list root directory.
        let mut p = drive::FilesListParams::default();
        p.q = Some("'root' in parents".to_string());

        let resp = cl.list(&p).await.expect("listing your Drive failed!");

        if let Some(files) = resp.files {
            for f in files {
                println!(
                    "{} => {:?}",
                    f.name.as_ref().unwrap_or(&"???".to_string()),
                    f
                );
            }
        }
    }
}
