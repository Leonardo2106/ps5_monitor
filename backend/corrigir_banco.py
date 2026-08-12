import sqlite3

from config import DATABASE_PATH


def main() -> None:
    print(f"Banco utilizado: {DATABASE_PATH}")

    connection = sqlite3.connect(DATABASE_PATH)
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        ORDER BY name
        """
    )
    tables = [row[0] for row in cursor.fetchall()]

    print("Tabelas encontradas:", tables)

    if "prices" not in tables:
        connection.close()
        raise RuntimeError(
            "A tabela 'prices' não existe neste banco. "
            "Confira o caminho exibido acima."
        )

    cursor.execute(
        """
        SELECT id, date, store, product, price
        FROM prices
        WHERE store = 'Amazon Brasil'
          AND product LIKE '%PlayStation 5%'
          AND price < 1500
        """
    )

    records = cursor.fetchall()

    print("\nRegistros incorretos encontrados:")
    for record in records:
        print(record)

    cursor.execute(
        """
        DELETE FROM prices
        WHERE store = 'Amazon Brasil'
          AND product LIKE '%PlayStation 5%'
          AND price < 1500
        """
    )

    deleted_prices = cursor.rowcount

    if "alert_events" in tables:
        cursor.execute(
            """
            DELETE FROM alert_events
            WHERE store = 'Amazon Brasil'
              AND product LIKE '%PlayStation 5%'
              AND price < 1500
            """
        )
        deleted_alerts = cursor.rowcount
    else:
        deleted_alerts = 0

    connection.commit()
    connection.close()

    print(f"\nPreços removidos: {deleted_prices}")
    print(f"Alertas removidos: {deleted_alerts}")


if __name__ == "__main__":
    main()