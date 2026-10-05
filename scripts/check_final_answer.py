from decimal import Decimal

from src.agent_nodes import final_answer_node


state = {
    "question": "What were the top 5 product categories by sales value in 2018?",
    "sql": """
        SELECT
            COALESCE(
                pct.product_category_name_english,
                p.product_category_name
            ) AS category,
            SUM(oi.price) AS sales_value
        FROM orders AS o
        JOIN order_items AS oi
            ON o.order_id = oi.order_id
        JOIN products AS p
            ON oi.product_id = p.product_id
        LEFT JOIN product_category_name_translation AS pct
            ON p.product_category_name = pct.product_category_name
        WHERE o.order_status = 'delivered'
          AND o.order_purchase_timestamp >= '2018-01-01'
          AND o.order_purchase_timestamp < '2019-01-01'
        GROUP BY COALESCE(
            pct.product_category_name_english,
            p.product_category_name
        )
        ORDER BY sales_value DESC
        LIMIT 5
    """,
    "query_result": [
        {
            "category": "health_beauty",
            "sales_value": Decimal("755724.50"),
        },
        {
            "category": "watches_gifts",
            "sales_value": Decimal("687855.20"),
        },
        {
            "category": "bed_bath_table",
            "sales_value": Decimal("532358.85"),
        },
        {
            "category": "sports_leisure",
            "sales_value": Decimal("517166.26"),
        },
        {
            "category": "computers_accessories",
            "sales_value": Decimal("496269.30"),
        },
    ],
    "answer": "",
}


result = final_answer_node(state)

print(result["answer"])