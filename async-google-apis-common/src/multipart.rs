//! Format and stream a multipart/related request, for uploads.

use hyper::{self, body::Bytes};
use radix64::STD;
use serde::Serialize;
use std::io::Write;

pub const MIME_BOUNDARY: &'static str = "PB0BHe6XN3O6Q4bpnWQgS1pKfMfglTZdifFvh8YIc2APj4Cz3C";

pub fn format_multipart<Req: Serialize>(req: &Req, data: Bytes) -> anyhow::Result<Bytes> {
    let meta = serde_json::to_string(req)?;
    let mut buf = Vec::with_capacity(meta.len() + (1.5 * (data.len() as f64)) as usize);

    // Write metadata.
    buf.write(format!("--{}\n", MIME_BOUNDARY).as_bytes())
        .unwrap();
    buf.write("Content-Type: application/json; charset=UTF-8\n\n".as_bytes())
        .unwrap();
    buf.write(meta.as_bytes())?;

    buf.write(format!("\n\n--{}\n", MIME_BOUNDARY).as_bytes())
        .unwrap();
    buf.write("Content-Transfer-Encoding: base64\n\n".as_bytes())
        .unwrap();

    // Write data contents.
    let mut ew = radix64::io::EncodeWriter::new(STD, buf);
    ew.write(data.as_ref())?;

    let mut buf = ew.finish()?;
    buf.write(format!("\n\n--{}--\n", MIME_BOUNDARY).as_bytes())
        .unwrap();
    Ok(Bytes::from(buf))
}
