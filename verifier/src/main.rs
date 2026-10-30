use serde::{Deserialize, Serialize};
use std::env;
use std::fs;
use std::io::{self, BufRead};
use std::process::ExitCode;
use time::format_description::well_known::Rfc3339;
use time::OffsetDateTime;

#[derive(Debug, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields)]
struct TrainingEvent {
    event_type: String,
    run_id: String,
    step: u64,
    loss: f64,
    gradient_norm: f64,
    batch_size: u64,
    timestamp: String,
}

#[derive(Serialize)]
struct VerificationResult {
    valid: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    event: Option<TrainingEvent>,
    #[serde(skip_serializing_if = "Option::is_none")]
    error: Option<String>,
}

fn validate(event: &TrainingEvent) -> Result<(), String> {
    if event.event_type != "training_step" {
        return Err("event_type must be 'training_step'".to_string());
    }
    if event.run_id.trim().is_empty() || event.run_id.len() > 128 {
        return Err("run_id must be a non-empty string of at most 128 characters".to_string());
    }
    if !event.loss.is_finite() {
        return Err("loss must be finite".to_string());
    }
    if !event.gradient_norm.is_finite() || event.gradient_norm < 0.0 {
        return Err("gradient_norm must be finite and non-negative".to_string());
    }
    if event.batch_size == 0 {
        return Err("batch_size must be positive".to_string());
    }
    OffsetDateTime::parse(&event.timestamp, &Rfc3339)
        .map_err(|_| "timestamp must be RFC 3339 with a timezone".to_string())?;
    Ok(())
}

fn verify_line(line: &str) -> VerificationResult {
    match serde_json::from_str::<TrainingEvent>(line) {
        Ok(event) => match validate(&event) {
            Ok(()) => {
                VerificationResult {
                    valid: true,
                    event: Some(event),
                    error: None,
                }
            }
            Err(error) => VerificationResult {
                valid: false,
                event: None,
                error: Some(error),
            },
        },
        Err(error) => VerificationResult {
            valid: false,
            event: None,
            error: Some(error.to_string()),
        },
    }
}

fn main() -> ExitCode {
    let args: Vec<String> = env::args().skip(1).collect();
    let input_lines: Vec<String> = match args.as_slice() {
        [] => io::stdin()
            .lock()
            .lines()
            .filter_map(Result::ok)
            .filter(|line| !line.trim().is_empty())
            .collect(),
        [path] => match fs::read_to_string(path) {
            Ok(contents) => vec![contents],
            Err(error) => {
                eprintln!("unable to read {path}: {error}");
                return ExitCode::from(2);
            }
        },
        _ => {
            eprintln!("usage: veyepr-verifier [event.json] < events.ndjson");
            return ExitCode::from(2);
        }
    };

    let mut invalid_count = 0;
    for line in input_lines {
        let result = verify_line(&line);
        if !result.valid {
            invalid_count += 1;
        }
        println!("{}", serde_json::to_string(&result).expect("serializable result"));
    }

    if invalid_count == 0 {
        ExitCode::SUCCESS
    } else {
        ExitCode::from(1)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn valid_event() -> TrainingEvent {
        TrainingEvent {
            event_type: "training_step".to_string(),
            run_id: "verification-run".to_string(),
            step: 42,
            loss: 0.183,
            gradient_norm: 0.91,
            batch_size: 32,
            timestamp: "2026-10-30T06:00:00+00:00".to_string(),
        }
    }

    #[test]
    fn accepts_the_contract_fixture_shape() {
        assert!(validate(&valid_event()).is_ok());
    }

    #[test]
    fn rejects_an_empty_run_identifier() {
        let mut event = valid_event();
        event.run_id.clear();
        assert!(validate(&event).is_err());
    }

    #[test]
    fn rejects_unknown_json_fields() {
        let result = serde_json::from_str::<TrainingEvent>(
            r#"{"event_type":"training_step","run_id":"run","step":1,"loss":1.0,"gradient_norm":1.0,"batch_size":1,"timestamp":"2026-10-30T06:00:00+00:00","unknown":true}"#,
        );
        assert!(result.is_err());
    }
}
