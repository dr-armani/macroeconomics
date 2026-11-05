"""
================================================================================
AI-AUTOMATION → UNEMPLOYMENT : EMPIRICALLY CALIBRATED SYSTEM DYNAMICS MODEL v2
================================================================================
CALIBRATION CHANGES FROM v1  (→ source):

  Parameter        v1        v2        Source
  ─────────────────────────────────────────────────────────────────────────────
  A0               0.06      0.78      McKinsey State of AI 2025: 78% of orgs
  adopt_rate       0.55      0.471     Fitted to McKinsey 2022→2025 jump (50%→78%)
  A_ceiling        0.95      0.95      unchanged
  LF0              168.0M    170.5M    BLS Jan 2025 actual
  E0               161.0M    163.8M    BLS Jan 2025 actual
  lf_growth        0.4%/yr   0.9%/yr   CBO 2025: 0.9% (2025-29), 0.4% (2030-35)
                             → 0.4%/yr
  prod_baseline    1.2%/yr   0.9%/yr   BLS MFP private nonfarm 2019-24 avg
  k_displace       0.62      0.39      A&R JPE 2020 PREFERRED spec (0.39pp/robot)
                                       (v1 used abstract/conservative 0.20→scaled)
  k_displace_abs   —         0.20      A&R JPE 2020 abstract (lower bound)
  k_reinstate      0.55      0.55      unchanged; A&R JEP 2019
  reinstate_lag    2.5 yr    2.5 yr    unchanged
  share_AI0        4%        3%        Enterprise AI spend ~1-3% of op. costs
  phi0             0.05      0.07      Slightly higher given 2025 deployments

KEY DATA ANCHORS:
  BLS MFP 2019-24: 0.9%/yr private nonfarm (prod3.htm Mar 2026)
  BLS MFP 2024 alone: 1.3%/yr (acceleration matching AI adoption)
  CBO LF growth: 0.9%/yr 2025-29, 0.4%/yr 2030-35 (publication 61189)
  BLS employment: 163.8M employed / 170.5M LF → u = 3.9% (Jan 2025)
  A&R JPE 2020: preferred spec = 0.39pp emp/pop per robot/1000 workers
                abstract/conservative = 0.20pp (NBER abstract)
  McKinsey survey: 50% (2019-22), 55% (2023), 72% (early 2024), 78% (2025)
  McKinsey 2025: 88% use AI in ≥1 function (late 2025 reading)
  IFR robots: 1.81 per 1000 workers (US 2017), est. ~3.0-3.5 by 2025
================================================================================
"""
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from dataclasses import dataclass

@dataclass
class Params:
    # Time
    t0: float = 2025.0
    t_end: float = 2040.0
    dt: float = 0.25

    # Labor market — BLS Jan 2025 actuals
    LF0: float = 170.5          # civilian LF millions (BLS Jan 2025)
    E0:  float = 163.8          # employment millions (BLS Jan 2025); u0 = 3.9%
    emp_adjust: float = 1.2     # DMP friction; Leduc & Liu (2020)

    # AI adoption — logistic, A0 = McKinsey 2025 observed value (78%)
    # Rate r=0.471 fitted to reproduce 50%→78% jump over 2022-2025
    A0:         float = 0.78
    adopt_rate: float = 0.471   # fitted to McKinsey time-series
    A_ceiling:  float = 0.95

    # Task automation
    phi0:             float = 0.07
    exposure_ceiling: float = 0.46  # IMF (2024) baseline; scenario-varied
    phi_gain:         float = 0.85

    # Displacement — A&R JPE 2020 preferred estimate
    k_displace: float = 0.39    # 0.39pp emp/pop per robot/1000 (JPE preferred)

    # Reinstatement — A&R JEP 2019
    k_reinstate:  float = 0.55
    reinstate_lag: float = 2.5  # David (1990) electrification analogy

    # Scale + capital deepening
    k_scale:  float = 0.45      # Autor & Salomons (2018)
    k_capdeep: float = 0.10

    # Productivity — BLS MFP calibrated
    prod_baseline:  float = 0.009   # BLS MFP private nonfarm 2019-24: 0.9%/yr
    prod_from_auto: float = 0.030   # GS (2023): ~1.5pp at full adoption

    # Firm budget shares — BEA 2024 + McKinsey AI spend estimates
    share_L0:  float = 0.58
    share_AI0: float = 0.03     # ~3% of operating costs (down from assumed 4%)
    share_E0:  float = 0.08
    share_M0:  float = 0.31

    # CES substitution
    sigma_LA: float = 1.8
    ai_price_decline: float = 0.20  # Epoch AI (2023): ~20%/yr compute decline

    singularity_phi: float = 0.90


# CBO split labor-force growth: 0.9%/yr 2025-29, 0.4%/yr 2030-35
def lf_growth(yr):
    return 0.009 if yr < 2030 else 0.004


SCENARIOS = {
    "Slow  (E_max=0.40, r=0.30)":  (0.30, 0.40, 0.020, "#2a9d8f"),
    "Base  (E_max=0.46, r=0.471)": (0.471, 0.46, 0.030, "#264653"),
    "Fast  (E_max=0.60, r=0.70)":  (0.70, 0.60, 0.045, "#e76f51"),
}


def simulate(p, adopt_rate, exposure_ceiling, prod_from_auto):
    t = np.arange(p.t0, p.t_end + p.dt, p.dt)
    n = len(t)
    A   = np.zeros(n); A[0]   = p.A0
    phi = np.zeros(n); phi[0] = p.phi0
    E   = np.zeros(n); E[0]   = p.E0
    LF  = np.zeros(n); LF[0]  = p.LF0
    Ld  = np.zeros(n); Ld[0]  = p.E0
    GDP = np.zeros(n); GDP[0] = 100.0
    prod= np.zeros(n)
    sL  = np.zeros(n); sL[0]  = p.share_L0
    sAI = np.zeros(n); sAI[0] = p.share_AI0
    sE  = np.zeros(n); sE[0]  = p.share_E0
    sM  = np.zeros(n); sM[0]  = p.share_M0
    u   = np.zeros(n); u[0]   = 1.0 - p.E0/p.LF0
    rel_price_AI = 1.0
    reinstate_buffer = []

    for i in range(1, n):
        dt = p.dt; yr = t[i]
        dA = adopt_rate * A[i-1] * (1.0 - A[i-1]/p.A_ceiling)
        A[i] = min(p.A_ceiling, A[i-1] + dA*dt)
        phi_target = exposure_ceiling * (A[i]**0.8)
        dphi = p.phi_gain * (phi_target - phi[i-1])
        phi[i] = max(0.0, phi[i-1] + dphi*dt)
        dphi_r = (phi[i]-phi[i-1])/dt
        prod[i] = p.prod_baseline + prod_from_auto*(phi[i]/max(exposure_ceiling,1e-6))
        GDP[i] = GDP[i-1]*(1.0+prod[i]*dt)
        reinstate_buffer.append(p.k_reinstate*prod[i]*dphi_r)
        lag_steps = int(p.reinstate_lag/dt)
        reinstatement = reinstate_buffer[i-1-lag_steps] if i-1-lag_steps>=0 else 0.0
        net_ldg = (-p.k_displace*dphi_r + reinstatement +
                   p.k_scale*prod[i] + p.k_capdeep*dA)
        Ld[i] = Ld[i-1]*(1.0+net_ldg*dt)
        LF[i] = LF[i-1]*(1.0+lf_growth(yr)*dt)
        E[i]  = min(E[i-1]+p.emp_adjust*(Ld[i]-E[i-1])*dt, LF[i])
        u[i]  = max(0.0, 1.0-E[i]/LF[i])
        rel_price_AI *= (1.0-p.ai_price_decline*dt)
        shift = rel_price_AI**(1.0-p.sigma_LA)
        raw_L   = p.share_L0*shift
        raw_AI  = p.share_AI0/max(shift,1e-6)*(1.0+6.0*phi[i])
        raw_E   = p.share_E0*(1.0+0.4*(A[i]-p.A0))
        raw_M   = p.share_M0
        tot = raw_L+raw_AI+raw_E+raw_M
        sL[i],sAI[i],sE[i],sM[i] = raw_L/tot,raw_AI/tot,raw_E/tot,raw_M/tot

    sing_idx = np.argmax(phi>=p.singularity_phi) if np.any(phi>=p.singularity_phi) else None
    return dict(t=t,A=A,phi=phi,u=u,E=E,LF=LF,GDP=GDP,prod=prod,
                sL=sL,sAI=sAI,sE=sE,sM=sM,
                sing_year=(t[sing_idx] if sing_idx else None))


def print_results(p, results):
    print("="*78)
    print("CALIBRATED v2 — Key Scenario Outputs")
    print(f"  u(2025) = {(1-p.E0/p.LF0)*100:.1f}%  LF={p.LF0}M  E={p.E0}M")
    print(f"  k_d={p.k_displace} (A&R JPE preferred)  TFP={p.prod_baseline*100:.1f}%/yr (BLS MFP)")
    print("="*78)
    years = [2025,2026,2027,2028,2029,2030,2031,2032,2033,2034,2035,2036,2037,2038,2039,2040]
    hdr = f"{'Year':<6}" + "".join(f"{'u%':>10}" for _ in SCENARIOS) + \
          "".join(f"{'GDP':>8}" for _ in SCENARIOS)
    print(f"\n{'Year':<6}" +
          "  u-Slow  u-Base  u-Fast" +
          " GDP-Slow GDP-Base GDP-Fast")
    print("-"*60)
    for yr in years:
        row = f"{yr:<6}"
        for name,(r,_) in results.items():
            idx = np.argmin(np.abs(r['t']-yr))
            row += f"  {r['u'][idx]*100:>5.1f}%"
        row += "  "
        for name,(r,_) in results.items():
            idx = np.argmin(np.abs(r['t']-yr))
            row += f" {r['GDP'][idx]:>7.1f}"
        print(row)
    print()
    for name,(r,_) in results.items():
        peak = r['u'].max()*100
        peak_yr = r['t'][np.argmax(r['u'])]
        print(f"{name}")
        print(f"  Peak unemployment: {peak:.1f}% in {peak_yr:.0f}")


def main():
    p = Params()
    results = {n:(simulate(p,*v[:3]),v[3]) for n,v in SCENARIOS.items()}
    print_results(p, results)

    # ── FIGURE: 2×3 ──────────────────────────────────────────────────────────
    fig = plt.figure(figsize=(16, 11))
    gs  = gridspec.GridSpec(2, 3, figure=fig, hspace=0.40, wspace=0.33)

    colors = [v[3] for v in SCENARIOS.values()]
    labels = [k.split("(")[0].strip() for k in SCENARIOS.keys()]

    # 1 — Unemployment
    ax1 = fig.add_subplot(gs[0,0])
    for (name,(r,c)), lbl in zip(results.items(), labels):
        ax1.plot(r["t"], r["u"]*100, color=c, lw=2.2, label=lbl)
    ax1.axhline((1-p.E0/p.LF0)*100, ls=":", c="gray", lw=1.2,
                label=f"2025 baseline {(1-p.E0/p.LF0)*100:.1f}%")
    ax1.set_title("Unemployment rate (%)"); ax1.set_xlabel("Year")
    ax1.legend(fontsize=7.5); ax1.grid(alpha=.3); ax1.set_ylim(0,20)
    ax1.annotate("k_d = 0.39\n(A&R JPE preferred)", xy=(2031,14),
                 fontsize=7, color="#555", style='italic')

    # 2 — Task automation
    ax2 = fig.add_subplot(gs[0,1])
    for (name,(r,c)), lbl in zip(results.items(), labels):
        ax2.plot(r["t"], r["phi"]*100, color=c, lw=2.2, label=lbl)
    ax2.axhline(p.singularity_phi*100, ls="--", c="red", lw=1, label="~Full-auto proxy")
    ax2.set_title("Tasks automated (%)"); ax2.set_xlabel("Year")
    ax2.legend(fontsize=7.5); ax2.grid(alpha=.3)

    # 3 — AI adoption backcast validation
    ax3 = fig.add_subplot(gs[0,2])
    t_back = np.arange(2019, 2041, 0.25)
    A_full = np.zeros(len(t_back)); A_full[0] = 0.50
    for i in range(1, len(t_back)):
        yr_b = t_back[i]
        r_use = 0.471 if yr_b >= 2022 else 0.02   # slow pre-GPT4, fast post
        dA = r_use*A_full[i-1]*(1-A_full[i-1]/0.95)
        A_full[i] = min(0.95, A_full[i-1]+dA*0.25)
    ax3.plot(t_back, A_full*100, color="#264653", lw=2.2, label="Model (two-phase)")
    mckinsey_yrs  = [2019, 2022, 2023, 2024, 2025]
    mckinsey_vals = [50,   50,   55,   72,   78  ]
    ax3.scatter(mckinsey_yrs, mckinsey_vals, color="#e76f51", s=70, zorder=5,
                label="McKinsey surveys")
    ax3.axvline(2025, ls=":", c="gray", lw=1)
    ax3.set_xlim(2019, 2040); ax3.set_ylim(0,100)
    ax3.set_title("AI adoption: model vs. McKinsey data")
    ax3.set_xlabel("Year"); ax3.set_ylabel("% orgs using AI in ≥1 function")
    ax3.legend(fontsize=7.5); ax3.grid(alpha=.3)
    ax3.text(2025.2, 20, "← historical fit | forecast →", fontsize=7, color="#555")

    # 4 — GDP
    ax4 = fig.add_subplot(gs[1,0])
    for (name,(r,c)), lbl in zip(results.items(), labels):
        ax4.plot(r["t"], r["GDP"], color=c, lw=2.2, label=lbl)
    ax4.set_title("GDP index (2025 = 100)"); ax4.set_xlabel("Year")
    ax4.legend(fontsize=7.5); ax4.grid(alpha=.3)
    ax4.annotate("TFP baseline = 0.9%/yr\n(BLS MFP 2019-24)", xy=(2026,103),
                 fontsize=7, color="#555", style='italic')

    # 5 — Budget shares (base)
    ax5 = fig.add_subplot(gs[1,1])
    base_key = "Base  (E_max=0.46, r=0.471)"
    base = results[base_key][0]
    ax5.stackplot(base["t"], base["sL"]*100, base["sAI"]*100,
                  base["sE"]*100, base["sM"]*100,
                  labels=["Labor","AI-capital","Energy","Materials"],
                  colors=["#264653","#e76f51","#e9c46a","#8ab17d"], alpha=.85)
    ax5.set_title("Firm budget shares — BASE (%)"); ax5.set_xlabel("Year")
    ax5.legend(loc="upper right", fontsize=7.5); ax5.set_ylim(0,100)

    # 6 — Parameter comparison table
    ax6 = fig.add_subplot(gs[1,2])
    ax6.axis('off')
    col_labels = ["Parameter", "v1\n(assumed)", "v2\n(empirical)", "Source"]
    rows = [
        ["k_d",           "0.62",     "0.39",      "A&R JPE 2020\npreferred spec"],
        ["TFP baseline",  "1.2%/yr",  "0.9%/yr",   "BLS MFP\n2019-24"],
        ["LF growth",     "0.4%/yr",  "0.9→0.4%",  "CBO 2025\nsplit rate"],
        ["A₀ (2025)",     "0.06",     "0.78",      "McKinsey\nState of AI 2025"],
        ["adopt rate r",  "0.55",     "0.471",     "Fitted to\nMcKinsey series"],
        ["E₀ / LF₀",      "161/168M", "164/170.5M","BLS Jan 2025"],
        ["s_AI₀",         "4%",       "3%",        "IT spend /\nop. costs 2025"],
        ["φ₀",            "5%",       "7%",        "2025 task-level\nAI estimates"],
    ]
    tbl = ax6.table(cellText=rows, colLabels=col_labels,
                    cellLoc='center', loc='center',
                    colWidths=[0.27,0.20,0.22,0.31])
    tbl.auto_set_font_size(False); tbl.set_fontsize(7)
    for (row, col), cell in tbl.get_celld().items():
        if row == 0:
            cell.set_facecolor('#264653')
            cell.set_text_props(color='white', fontweight='bold')
        elif row % 2 == 0:
            cell.set_facecolor('#eef2f7')
        cell.set_height(0.11)
    ax6.set_title("Calibration: assumed → empirical", fontsize=9, pad=14)

    plt.suptitle(
        "AI-Automation Unemployment Model — Empirically Calibrated (v2)\n"
        "k_d=0.39 (A&R JPE preferred) · TFP=0.9%/yr (BLS MFP 2019-24) · "
        "LF growth per CBO 2025 · A(t) fitted to McKinsey surveys 2022-2025",
        fontsize=9.5, y=1.02)
    plt.savefig("/mnt/user-data/outputs/ai_unemployment_calibrated.png",
                dpi=130, bbox_inches='tight')
    print("Saved → ai_unemployment_calibrated.png")
    plt.show()


if __name__ == "__main__":
    main()
