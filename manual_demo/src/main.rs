// A manual client for a Google API (e.g. Drive), to test what makes sense and what doesn't.

use yup_oauth2::InstalledFlowAuthenticator;
use std::string::String;
use std::str::FromStr;

use hyper::Uri;
use hyper_rustls::HttpsConnector;
use serde_json::Value;

type TlsConnr = HttpsConnector<hyper::client::HttpConnector>;
type TlsClient = hyper::Client<TlsConnr, hyper::Body>;

fn https_client() -> TlsClient {
    let conn = hyper_rustls::HttpsConnector::new();
    let cl = hyper::Client::builder().build(conn);
    cl
}

async fn get_about(cl: &mut TlsClient, auth: &mut yup_oauth2::authenticator::Authenticator<TlsConnr>) {
    let baseurl = "https://www.googleapis.com/drive/v3/";
    let path = "about";
    let tok = auth.token(&["https://www.googleapis.com/auth/drive.file"]).await.unwrap();
    let authtok = format!("?oauth_token={}&fields=*", tok.as_str());

    let resp = cl.get(Uri::from_str(&(String::from(baseurl)+path+&authtok)).unwrap()).await.unwrap();
    let body = resp.into_body();
    let body = hyper::body::to_bytes(body).await.unwrap();
    let dec = String::from_utf8(body.to_vec()).unwrap();
    println!("{}", dec);
}

#[tokio::main]
async fn main() {
    let sec = yup_oauth2::read_application_secret("client_secret.json")
        .await
        .expect("client secret couldn't be read.");

    let mut auth = InstalledFlowAuthenticator::builder(sec, yup_oauth2::InstalledFlowReturnMethod::HTTPRedirect)
        .persist_tokens_to_disk("tokencache.json")
        .build()
        .await
        .expect("installed flow authenticator!");

    let scopes = &["https://www.googleapis.com/auth/drive.file"];

    let mut cl = https_client();

    get_about(&mut cl, &mut auth).await;

    match auth.token(scopes).await {
        Ok(token) => println!("The token is {:?}", token),
        Err(e) => println!("error: {:?}", e),
    }
}
