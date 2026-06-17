# app/streamlit_app.py
"""Lacuna dashboard (PRD §14). Reads distilled Supabase tables for responsiveness.
Both modes (Single-Title + Category Sweep), provenance on every panel, a timely↔
evergreen slider whose freshness indicator DIMS toward 'timely' (honest signal that
the fresh layer is thinner), empty/loading/error states, and Context Pack download
(JSON + Markdown). No raw review text is ever surfaced — only paraphrased clusters."""
from __future__ import annotations

import asyncio
import json

import streamlit as st
from sqlalchemy import func, select

from lacuna.config import load_default
from lacuna.db.models import AspectCluster, Project, Review, Score, Work
from lacuna.db.session import build_sessionmaker
from lacuna.export.context_pack import Candidate, Complaint, build_pack, to_markdown
from lacuna.pipeline.freshness import freshness_opacity

st.set_page_config(page_title="Lacuna — Reader-Gap Engine", layout="wide")


def _run(coro):
    return asyncio.run(coro)


@st.cache_data(show_spinner=False)
def load_projects() -> list[tuple[str, str]]:
    async def _go():
        sm = build_sessionmaker()
        async with sm() as s:
            rows = (await s.execute(select(Project.id, Project.name))).all()
        return [(str(i), n) for i, n in rows]
    return _run(_go())


@st.cache_data(show_spinner=True)
def load_project_data(project_id: str) -> dict:
    async def _go():
        sm = build_sessionmaker()
        async with sm() as s:
            works = (await s.execute(select(Work).where(Work.project_id == project_id))).scalars().all()
            clusters = (await s.execute(select(AspectCluster).where(AspectCluster.project_id == project_id))).scalars().all()
            scores = (await s.execute(select(Score).where(Score.project_id == project_id))).scalars().all()
            rc = (await s.execute(select(Review.work_id, func.count()).where(
                Review.project_id == project_id).group_by(Review.work_id))).all()
        cbw: dict = {}
        for c in clusters:
            cbw.setdefault(str(c.work_id), []).append(c)
        return {
            "works": {str(w.id): w for w in works},
            "clusters_by_work": cbw,
            "scores": scores,
            "review_counts": {str(wid): n for wid, n in rc},
            "total_reviews": sum(n for _, n in rc),
        }
    return _run(_go())


def _provenance(data: dict, platforms: list[str]) -> None:
    st.caption(
        f"Provenance — platforms: {', '.join(platforms) or 'none'} · "
        f"works: {len(data['works'])} · reviews: {data['total_reviews']} · "
        f"scores: {len(data['scores'])}. Treat every candidate as a hypothesis, not a finding."
    )


def _freshness_indicator(slider: float) -> None:
    opacity = freshness_opacity(slider)
    label = "evergreen depth" if slider < 0.5 else "timely / fresh"
    st.markdown(
        f"<div style='padding:6px 10px;border-radius:6px;background:rgba(46,134,222,{opacity:.2f});'>"
        f"Freshness emphasis: <b>{label}</b> · indicator opacity {opacity:.2f} "
        f"(dimmer = fresh layer is thinner, lower confidence)</div>",
        unsafe_allow_html=True,
    )


def _complaints_for(data: dict, work_id: str, limit: int = 6) -> list[AspectCluster]:
    return sorted(data["clusters_by_work"].get(work_id, []),
                  key=lambda c: c.reviewer_count, reverse=True)[:limit]


def _build_pack(project_name: str, data: dict, mode: str) -> dict:
    cfg = load_default()
    cands = []
    for sc in data["scores"]:
        w = data["works"].get(sc.ref_id)
        if w is None:
            continue
        cands.append(Candidate(
            ref=sc.scope, title_or_subject=w.title,
            gap_score=float(sc.gap_score) if sc.gap_score is not None else 0.0,
            demand=float(sc.demand_score or 0.0), supply_scarcity=float(sc.supply_scarcity or 0.0),
            unmet_need=float(sc.unmet_need or 0.0), confidence=float(sc.confidence),
            sample_size=sc.sample_size, platforms=list(sc.platforms_used or []),
            oldest_signal=sc.oldest_signal.isoformat() if sc.oldest_signal else None,
            newest_signal=sc.newest_signal.isoformat() if sc.newest_signal else None,
            incomplete=sc.incomplete, blind_spot=sc.blind_spot,
            recent_supply_surge=sc.recent_supply_surge,
            top_complaints=[Complaint(c.representative or c.label, c.reviewer_count,
                                      float(c.helpful_weight or 0.0), list(c.platforms),
                                      bool(c.cross_platform)) for c in _complaints_for(data, sc.ref_id)],
            demand_evidence={},
        ))
    return build_pack(
        project=project_name, bisac=cfg.get("target_bisac", []), mode=mode,
        generated_at="dashboard", platforms_used=["amazon_corpus"],
        total_reviews=data["total_reviews"], cross_platform_agreement_pct=0.0,
        candidates=cands, max_candidates=int(cfg.get("export", {}).get("max_candidates", 15)))


def _download_buttons(pack: dict, key: str) -> None:
    st.download_button("⬇ Context Pack (JSON)", json.dumps(pack, indent=2, ensure_ascii=False),
                       file_name="lacuna_pack.json", mime="application/json", key=f"{key}_json")
    st.download_button("⬇ Context Pack (Markdown)", to_markdown(pack),
                       file_name="lacuna_pack.md", mime="text/markdown", key=f"{key}_md")


# ---- Sidebar ----
st.sidebar.title("Lacuna")
try:
    projects = load_projects()
except Exception as e:  # connection/credentials error -> honest error state
    st.error(f"Could not reach Supabase. Check DATABASE_URL in .env.\n\n{type(e).__name__}: {e}")
    st.stop()

if not projects:
    st.info("No projects yet. Run `lacuna seed` to populate the database, then reload.")
    st.stop()

name_by_id = {pid: name for pid, name in projects}
sel_id = st.sidebar.selectbox("Project", options=[p[0] for p in projects],
                              format_func=lambda i: name_by_id[i])
slider = st.sidebar.slider("Timely ↔ Evergreen", 0.0, 1.0,
                           value=float(load_default().get("timely_vs_evergreen", 0.5)), step=0.05,
                           help="0 = evergreen depth · 1 = timely/fresh (dims the freshness indicator)")
_freshness_indicator(slider)

data = load_project_data(sel_id)
project_name = name_by_id[sel_id]
st.title(f"Lacuna — {project_name}")

tab_single, tab_sweep = st.tabs(["Single-Title Watchlist", "Category Sweep (advanced)"])

with tab_single:
    _provenance(data, ["amazon_corpus"])
    if not data["works"]:
        st.info("No works seeded for this project yet.")
    else:
        titles = {wid: w.title for wid, w in data["works"].items()}
        wid = st.selectbox("Work", options=list(titles), format_func=lambda i: titles[i])
        w = data["works"][wid]
        c1, c2, c3 = st.columns(3)
        c1.metric("Reviews", data["review_counts"].get(wid, 0))
        c2.metric("Avg rating", f"{float(w.agg_rating_avg):.2f}" if w.agg_rating_avg is not None else "—")
        c3.metric("Editions", w.edition_count)
        st.subheader("Clustered complaints (paraphrased — no raw quotes)")
        comps = _complaints_for(data, wid, limit=20)
        if not comps:
            st.write("No complaint clusters for this work.")
        for c in comps:
            badge = "🔗 cross-platform" if c.cross_platform else f"· {', '.join(c.platforms)}"
            st.markdown(f"- **{c.representative or c.label}** — reviewers {c.reviewer_count}, "
                        f"helpful weight {float(c.helpful_weight or 0):.1f} {badge}")
        pack = _build_pack(project_name, data, "single_title")
        _download_buttons(pack, "single")

with tab_sweep:
    st.warning("Advanced mode: category-level candidates are lower-confidence than single-title analysis.")
    _provenance(data, ["amazon_corpus"])
    if not data["scores"]:
        st.info("No scores yet. Run `lacuna sweep` (or `lacuna export`) to compute gap scores, then reload.")
    else:
        ranked = sorted(data["scores"],
                        key=lambda s: (s.gap_score is not None, s.gap_score or 0.0), reverse=True)
        for sc in ranked:
            w = data["works"].get(sc.ref_id)
            if w is None:
                continue
            flags = [f for f, on in (("incomplete", sc.incomplete), ("blind_spot", sc.blind_spot),
                                     ("recent_supply_surge", sc.recent_supply_surge)) if on]
            gap = f"{float(sc.gap_score):.3f}" if sc.gap_score is not None else "withheld (incomplete)"
            with st.expander(f"{w.title} — gap {gap} · confidence {float(sc.confidence):.2f}"
                             + (f" · ⚠ {', '.join(flags)}" if flags else "")):
                st.write(f"sample_size={sc.sample_size} · platforms={', '.join(sc.platforms_used or [])}")
                for c in _complaints_for(data, sc.ref_id):
                    st.markdown(f"- {c.representative or c.label} (reviewers {c.reviewer_count})")
        pack = _build_pack(project_name, data, "category_sweep")
        _download_buttons(pack, "sweep")
