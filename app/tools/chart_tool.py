"""Chart Tool — generates Plotly chart data from query results.

Returns chart configs that Streamlit can render directly with st.plotly_chart().
Also integrates with Lightdash adapter for chart configuration context.
"""

from __future__ import annotations

from typing import Any

from app.adapters.lightdash_adapter import get_chart_config


def build_chart(
    chart_data: list[dict[str, Any]],
    chart_type: str = "bar",
    title: str = "",
    metric_name: str | None = None,
) -> dict[str, Any] | None:
    """Build a Plotly-compatible chart specification from query results.

    Args:
        chart_data: list of dicts with 'category' and 'amount' keys
        chart_type: 'bar', 'line', or 'pie'
        title: chart title
        metric_name: optional Lightdash metric name for config enrichment

    Returns:
        dict with 'type', 'data', 'layout' keys for Plotly rendering,
        or None if no data.
    """
    if not chart_data:
        return None

    categories = [str(row.get("category", "")) for row in chart_data]
    values = [float(row.get("amount", 0)) for row in chart_data]

    # Get Lightdash chart config if metric specified
    lh_config = {}
    if metric_name:
        lh_config = get_chart_config(metric_name, chart_type)

    colors = lh_config.get("config", {}).get(
        "colors", ["#4C78A8", "#F58518", "#E45756", "#72B7B2", "#54A24B"]
    )

    if chart_type == "bar":
        trace = {
            "type": "bar",
            "x": categories,
            "y": values,
            "marker": {"color": colors[:len(categories)]},
        }
    elif chart_type == "line":
        trace = {
            "type": "scatter",
            "mode": "lines+markers",
            "x": categories,
            "y": values,
            "line": {"color": colors[0], "width": 2},
            "marker": {"size": 8},
        }
    elif chart_type == "pie":
        trace = {
            "type": "pie",
            "labels": categories,
            "values": values,
            "marker": {"colors": colors[:len(categories)]},
        }
    else:
        trace = {
            "type": "bar",
            "x": categories,
            "y": values,
            "marker": {"color": colors[:len(categories)]},
        }

    layout = {
        "title": {"text": title or lh_config.get("title", ""), "font": {"size": 16}},
        "xaxis": {"title": ""},
        "yaxis": {"title": "Amount ($)", "tickprefix": "$"},
        "template": "plotly_white",
        "height": 400,
        "margin": {"l": 60, "r": 30, "t": 50, "b": 60},
    }

    return {
        "type": chart_type,
        "data": [trace],
        "layout": layout,
        "lightdash_config": lh_config if metric_name else None,
    }
