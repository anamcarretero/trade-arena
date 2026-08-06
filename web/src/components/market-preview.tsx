import type {Locale} from "@/lib/i18n";
import {copy} from "@/lib/i18n";

export function MarketPreview({locale}: {locale: Locale}) {
  const text = copy[locale];
  return <div className="market-stage" aria-hidden="true">
    <div className="market-glow market-glow-blue" />
    <div className="market-glow market-glow-violet" />
    <div className="market-window market-window-ghost">
      <div className="ghost-candles" />
    </div>
    <div className="market-window">
      <div className="market-toolbar">
        <div className="window-dots"><span /><span /><span /></div>
        <span className="market-title">TradeArena / {text.previewLabel}</span>
        <span className="live-pill"><i />{text.previewLive}</span>
      </div>
      <div className="chart-area">
        <div className="chart-grid" />
        <svg className="chart-lines" viewBox="0 0 960 360" preserveAspectRatio="none">
          <defs>
            <linearGradient id="line-blue" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0" stopColor="#00c2ff" />
              <stop offset="1" stopColor="#2962ff" />
            </linearGradient>
            <linearGradient id="line-violet" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0" stopColor="#7047eb" />
              <stop offset="1" stopColor="#e040fb" />
            </linearGradient>
            <linearGradient id="area-blue" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="#2962ff" stopOpacity=".28" />
              <stop offset="1" stopColor="#2962ff" stopOpacity="0" />
            </linearGradient>
          </defs>
          <path className="area-path" d="M0 286 C55 270 90 306 142 246 S230 118 300 168 S390 245 446 205 S522 112 590 146 S675 280 744 218 S840 102 960 78 L960 360 L0 360 Z" />
          <path className="line line-blue" d="M0 286 C55 270 90 306 142 246 S230 118 300 168 S390 245 446 205 S522 112 590 146 S675 280 744 218 S840 102 960 78" />
          <path className="line line-violet" d="M0 214 C72 200 106 138 160 170 S232 270 302 236 S392 104 456 122 S520 255 590 236 S690 104 758 142 S850 236 960 170" />
        </svg>
        <div className="chart-metric"><strong>+12.84%</strong><span>{text.previewPeriod}</span></div>
        <div className="chart-axis"><span>APR</span><span>MAY</span><span>JUN</span><span>JUL</span><span>AUG</span></div>
      </div>
    </div>
    <div className="market-summary">
      <div><span>{text.previewLabel}</span><strong>TA / 01</strong></div>
      <div className="summary-return"><span>{text.previewPeriod}</span><strong>+12.84%</strong></div>
      <span className="summary-arrow">↗</span>
    </div>
  </div>;
}
