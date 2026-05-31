use rusqlite::Connection;
use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize)]
pub struct HistoryEntry {
    pub id: i64,
    pub created_at: String,
    pub latex: String,
    pub backend: String,
    pub confidence: f64,
    pub screenshot_path: Option<String>,
    pub mathml: Option<String>,
}

#[allow(dead_code)]
pub fn insert(
    conn: &Connection,
    latex: &str,
    backend: &str,
    confidence: f64,
    screenshot_path: Option<&str>,
) -> Result<i64, rusqlite::Error> {
    conn.execute(
        "INSERT INTO history (latex, backend, confidence, screenshot_path) VALUES (?1, ?2, ?3, ?4)",
        (latex, backend, confidence, screenshot_path),
    )?;
    Ok(conn.last_insert_rowid())
}

pub fn list(
    conn: &Connection,
    limit: i64,
    offset: i64,
) -> Result<Vec<HistoryEntry>, rusqlite::Error> {
    let mut stmt = conn.prepare(
        "SELECT id, created_at, latex, backend, confidence, screenshot_path, mathml \
         FROM history ORDER BY created_at DESC LIMIT ?1 OFFSET ?2",
    )?;
    let entries = stmt
        .query_map((limit, offset), |row| {
            Ok(HistoryEntry {
                id: row.get(0)?,
                created_at: row.get(1)?,
                latex: row.get(2)?,
                backend: row.get(3)?,
                confidence: row.get(4)?,
                screenshot_path: row.get(5)?,
                mathml: row.get(6)?,
            })
        })?
        .collect::<Result<Vec<_>, _>>()?;
    Ok(entries)
}

pub fn get_by_id(conn: &Connection, id: i64) -> Result<Option<HistoryEntry>, rusqlite::Error> {
    let mut stmt = conn.prepare(
        "SELECT id, created_at, latex, backend, confidence, screenshot_path, mathml \
         FROM history WHERE id = ?1",
    )?;
    let mut entries = stmt.query_map([id], |row| {
        Ok(HistoryEntry {
            id: row.get(0)?,
            created_at: row.get(1)?,
            latex: row.get(2)?,
            backend: row.get(3)?,
            confidence: row.get(4)?,
            screenshot_path: row.get(5)?,
            mathml: row.get(6)?,
        })
    })?;
    match entries.next() {
        Some(entry) => Ok(Some(entry?)),
        None => Ok(None),
    }
}

pub fn delete(conn: &Connection, id: i64) -> Result<bool, rusqlite::Error> {
    let rows = conn.execute("DELETE FROM history WHERE id = ?1", [id])?;
    Ok(rows > 0)
}

pub fn search(conn: &Connection, query: &str) -> Result<Vec<HistoryEntry>, rusqlite::Error> {
    let trimmed = query.trim();
    if trimmed.is_empty() {
        return Ok(Vec::new());
    }
    // FTS5 phrase query: all chars literal except `"` (doubled here)
    let escaped_query = format!("\"{}\"", trimmed.replace('"', "\"\""));
    let mut stmt = conn.prepare(
        "SELECT h.id, h.created_at, h.latex, h.backend, h.confidence, h.screenshot_path, h.mathml
         FROM history h
         JOIN history_fts fts ON h.id = fts.rowid
         WHERE history_fts MATCH ?1
         ORDER BY h.created_at DESC",
    )?;
    let entries = stmt
        .query_map([&escaped_query as &str], |row| {
            Ok(HistoryEntry {
                id: row.get(0)?,
                created_at: row.get(1)?,
                latex: row.get(2)?,
                backend: row.get(3)?,
                confidence: row.get(4)?,
                screenshot_path: row.get(5)?,
                mathml: row.get(6)?,
            })
        })?
        .collect::<Result<Vec<_>, _>>()?;
    Ok(entries)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::db;

    fn setup_db() -> Connection {
        let conn = Connection::open_in_memory().unwrap();
        db::initialize_database(&conn).unwrap();
        conn
    }

    #[test]
    fn test_insert_and_get() {
        let conn = setup_db();
        let id = insert(&conn, "x^2", "pix2text", 0.95, Some("/tmp/shot.png")).unwrap();
        assert!(id > 0);

        let entry = get_by_id(&conn, id).unwrap().unwrap();
        assert_eq!(entry.latex, "x^2");
        assert_eq!(entry.backend, "pix2text");
        assert!((entry.confidence - 0.95).abs() < f64::EPSILON);
        assert_eq!(entry.screenshot_path.as_deref(), Some("/tmp/shot.png"));
    }

    #[test]
    fn test_list_pagination() {
        let conn = setup_db();
        for i in 0..5 {
            insert(&conn, &format!("formula_{}", i), "test", 0.9, None).unwrap();
        }

        let page1 = list(&conn, 2, 0).unwrap();
        assert_eq!(page1.len(), 2);

        let page2 = list(&conn, 2, 2).unwrap();
        assert_eq!(page2.len(), 2);

        let page3 = list(&conn, 2, 4).unwrap();
        assert_eq!(page3.len(), 1);
    }

    #[test]
    fn test_get_nonexistent() {
        let conn = setup_db();
        let result = get_by_id(&conn, 999).unwrap();
        assert!(result.is_none());
    }

    #[test]
    fn test_delete() {
        let conn = setup_db();
        let id = insert(&conn, "to_delete", "test", 0.8, None).unwrap();

        assert!(delete(&conn, id).unwrap());
        assert!(get_by_id(&conn, id).unwrap().is_none());

        // Deleting non-existent should return false
        assert!(!delete(&conn, id).unwrap());
    }

    #[test]
    fn test_search() {
        let conn = setup_db();
        insert(&conn, "x^2 + y^2", "pix2text", 0.95, None).unwrap();
        insert(&conn, "\\sin(\\theta)", "test", 0.9, None).unwrap();
        insert(&conn, "x^3", "pix2text", 0.85, None).unwrap();

        let results = search(&conn, "x^2").unwrap();
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].latex, "x^2 + y^2");

        let results = search(&conn, "sin").unwrap();
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].latex, "\\sin(\\theta)");
    }

    #[test]
    fn test_search_empty() {
        let conn = setup_db();
        insert(&conn, "x^2", "test", 0.9, None).unwrap();

        let results = search(&conn, "nonexistent").unwrap();
        assert!(results.is_empty());
    }

    #[test]
    fn test_search_empty_query() {
        let conn = setup_db();
        insert(&conn, "x^2", "test", 0.9, None).unwrap();

        assert!(search(&conn, "").unwrap().is_empty());
        assert!(search(&conn, "   ").unwrap().is_empty());
    }

    #[test]
    fn test_search_special_chars() {
        let conn = setup_db();
        insert(&conn, "x^2 + y^2", "test", 0.9, None).unwrap();
        insert(&conn, "a*b", "test", 0.9, None).unwrap();
        insert(&conn, "c:d", "test", 0.9, None).unwrap();
        insert(&conn, "e{f}g", "test", 0.9, None).unwrap();

        assert_eq!(search(&conn, "x^2").unwrap().len(), 1);
        assert_eq!(search(&conn, "a*b").unwrap().len(), 1);
        assert_eq!(search(&conn, "c:d").unwrap().len(), 1);
        assert_eq!(search(&conn, "e{f}g").unwrap().len(), 1);
    }
}
