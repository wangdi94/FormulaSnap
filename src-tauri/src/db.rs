use rusqlite::{Connection, Result};

/// Initialize the SQLite database schema.
/// This function is idempotent - safe to call multiple times.
pub fn initialize_database(conn: &Connection) -> Result<()> {
    conn.execute_batch("PRAGMA journal_mode=WAL;")?;
    conn.execute_batch("PRAGMA wal_checkpoint(TRUNCATE);")?;

    // Create history table
    conn.execute_batch(
        "CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            latex TEXT NOT NULL,
            backend TEXT NOT NULL,
            confidence REAL NOT NULL,
            screenshot_path TEXT,
            mathml TEXT
        );",
    )?;

    // Create settings table
    conn.execute_batch(
        "CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );",
    )?;

    // Create FTS5 virtual table for full-text search
    conn.execute_batch(
        "CREATE VIRTUAL TABLE IF NOT EXISTS history_fts USING fts5(
            latex,
            content='history',
            content_rowid='id'
        );",
    )?;

    // Create triggers to keep FTS table in sync
    conn.execute_batch(
        "CREATE TRIGGER IF NOT EXISTS history_ai AFTER INSERT ON history BEGIN
            INSERT INTO history_fts(rowid, latex) VALUES (new.id, new.latex);
        END;
        
        CREATE TRIGGER IF NOT EXISTS history_ad AFTER DELETE ON history BEGIN
            INSERT INTO history_fts(history_fts, rowid, latex) VALUES('delete', old.id, old.latex);
        END;
        
        CREATE TRIGGER IF NOT EXISTS history_au AFTER UPDATE ON history BEGIN
            INSERT INTO history_fts(history_fts, rowid, latex) VALUES('delete', old.id, old.latex);
            INSERT INTO history_fts(rowid, latex) VALUES (new.id, new.latex);
        END;",
    )?;

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use rusqlite::Connection;

    #[test]
    fn test_tables_created() {
        let conn = Connection::open_in_memory().unwrap();
        initialize_database(&conn).unwrap();

        // Check history table exists
        let count: i64 = conn
            .query_row(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='history'",
                [],
                |row| row.get(0),
            )
            .unwrap();
        assert_eq!(count, 1);

        // Check settings table exists
        let count: i64 = conn
            .query_row(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='settings'",
                [],
                |row| row.get(0),
            )
            .unwrap();
        assert_eq!(count, 1);
    }

    #[test]
    fn test_fts5_search() {
        let conn = Connection::open_in_memory().unwrap();
        initialize_database(&conn).unwrap();

        // Insert test data
        conn.execute(
            "INSERT INTO history (latex, backend, confidence) VALUES (?1, ?2, ?3)",
            ["\\frac{a}{b}", "pix2text", "0.95"],
        )
        .unwrap();

        // Search using FTS5
        let result: String = conn
            .query_row(
                "SELECT latex FROM history_fts WHERE history_fts MATCH 'frac'",
                [],
                |row| row.get(0),
            )
            .unwrap();
        assert_eq!(result, "\\frac{a}{b}");
    }

    #[test]
    fn test_migration_idempotent() {
        let conn = Connection::open_in_memory().unwrap();
        // Run migration twice
        initialize_database(&conn).unwrap();
        initialize_database(&conn).unwrap();
        // Should not fail
    }
}
