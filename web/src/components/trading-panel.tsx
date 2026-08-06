import type {Portfolio, Ranking} from "../lib/api";
import {copy, type Locale} from "../lib/i18n";
import {
  cancelOrder, correctReportedTrade, reportTrade, submitOrder
} from "../app/[locale]/app/leagues/actions";
import {CommissionField} from "./commission-field";

export function TradingPanel({locale, leagueId, competitionId, portfolio, ranking}: {
  locale: Locale;
  leagueId: string;
  competitionId: string;
  portfolio: Portfolio;
  ranking: Ranking;
}) {
  const text = copy[locale];
  const correctedExecutions = new Set(
    portfolio.executions.flatMap(execution => execution.correction_of ? [execution.correction_of] : [])
  );
  return <div className="trading-panel">
    <h3>{text.trading}</h3>
    {portfolio.joined_late && <div className="late-entry" role="status">
      <strong>{text.lateJoiner}</strong><span>{text.lateJoinerExplanation}</span>
    </div>}
    <div className="portfolio-metrics">
      <Metric label={text.availableCash} value={`${portfolio.cash} ${portfolio.currency}`}/>
      <Metric label={text.portfolioValue} value={`${portfolio.equity} ${portfolio.currency}`}/>
      <Metric label={text.cumulativeReturn} value={formatPercent(portfolio.cumulative_return, locale)}/>
    </div>
    <div className="trading-grid">
      <section className="trade-card">
        <h4>{text.newOrder}</h4>
        <form action={submitOrder} className="order-form">
          <References locale={locale} leagueId={leagueId} competitionId={competitionId}/>
          <label>{text.symbol}<input name="symbol" required maxLength={16} pattern="[A-Za-z][A-Za-z0-9.\-]*" autoCapitalize="characters"/></label>
          <label>{text.side}<select name="side"><option value="buy">{text.buy}</option><option value="sell">{text.sell}</option></select></label>
          <label>{text.shares}<input name="quantity" type="number" min="0.00000001" step="0.00000001" required/></label>
          <label>{text.orderType}<select name="order_type"><option value="market">{text.marketOrder}</option><option value="limit">{text.limitOrder}</option></select></label>
          <label>{text.limitPrice}<input name="limit_price" inputMode="decimal" pattern="\d+(\.\d{1,4})?"/></label>
          <label>{text.optionalCommission}<input name="commission" inputMode="decimal" pattern="[0-9]+([.,][0-9]{1,2})?"/><small>{text.orderCommissionHelp}</small></label>
          <label className="checkbox-row"><input name="allow_extended_hours" type="checkbox"/>{text.extendedHours}</label>
          <button className="primary" type="submit">{text.submitOrder}<span aria-hidden="true">→</span></button>
        </form>
      </section>
      <section className="trade-card">
        <h4>{text.reportedTrade}</h4>
        <p className="empty-copy">{text.reportedTradeIntro}</p>
        <form action={reportTrade} className="order-form">
          <References locale={locale} leagueId={leagueId} competitionId={competitionId}/>
          <label>{text.tradeDate}<input name="date" type="datetime-local" required/></label>
          <label>{text.timezone}<select name="timezone" defaultValue="Europe/Madrid"><option value="Europe/Madrid">{text.madridTime}</option><option value="UTC">{text.utcTime}</option></select></label>
          <label>{text.symbol}<input name="ticker" required maxLength={16} pattern="[A-Za-z][A-Za-z0-9.\-]*" autoCapitalize="characters"/></label>
          <label>{text.side}<select name="type"><option value="buy">{text.buy}</option><option value="sell">{text.sell}</option></select></label>
          <label>{text.shares}<input name="quantity" type="number" min="0.00000001" step="0.00000001" required/></label>
          <label>{text.pricePerShare}<input name="price_per_share" inputMode="decimal" pattern="[0-9]+([.,][0-9]{1,4})?" required/></label>
          <label>{text.totalAmount}<input name="total_amount" inputMode="decimal" pattern="[0-9]+([.,][0-9]{1,2})?" required/></label>
          <CommissionField label={text.optionalCommission} help={text.commissionAutoHelp}/>
          <div className="reported-constants"><span>{text.currency}: <strong>USD</strong></span><span>{text.fxRate}: <strong>1</strong></span></div>
          <button className="primary" type="submit">{text.reportTrade}<span aria-hidden="true">→</span></button>
        </form>
      </section>
      <section className="trade-card">
        <h4>{text.positions}</h4>
        {portfolio.positions.length === 0 ? <p className="empty-copy">{text.noPositions}</p> :
          <div className="compact-list">{portfolio.positions.map(position =>
            <div key={position.symbol}><strong>{position.symbol}</strong><span>{position.quantity} · {position.market_value} USD</span></div>)}</div>}
      </section>
      <section className="trade-card wide-card">
        <h4>{text.orderHistory}</h4>
        {portfolio.orders.length === 0 ? <p className="empty-copy">{text.noOrders}</p> :
          <div className="history-list">{portfolio.orders.map(order => <article key={order.id}>
            <div><strong>{order.side === "buy" ? text.buy : text.sell} {order.quantity} {order.symbol}</strong><span>{order.order_type === "market" ? text.marketOrder : `${text.limitOrder} · ${order.limit_price} USD`}</span></div>
            <div className="history-status"><span className={`status-pill ${order.status}`}>{text[order.status]}</span>
              {order.status === "pending" && <form action={cancelOrder}>
                <References locale={locale} leagueId={leagueId} competitionId={competitionId}/>
                <input type="hidden" name="order_id" value={order.id}/><button className="danger-button" type="submit">{text.cancelOrder}</button>
              </form>}
            </div>
          </article>)}</div>}
      </section>
      <section className="trade-card">
        <h4>{text.executions}</h4>
        {portfolio.executions.length === 0 ? <p className="empty-copy">{text.noExecutions}</p> :
          <div className="compact-list">{portfolio.executions.map(execution =>
            <div key={execution.id}><strong>{execution.quantity} {execution.symbol} · {execution.price} USD</strong>
              <span>{text.commission}: {execution.commission} USD · {execution.session}</span>
              <span className={`source-pill ${execution.source}`}>{execution.source === "fixture" ? text.fixtureExecution : text.reportedExecution}</span>
              {execution.correction_of && <span>{text.compensatesExecution}</span>}
              {correctedExecutions.has(execution.id) && <span>{text.correctedExecution}</span>}
              {execution.source === "reported" && !execution.correction_of && !correctedExecutions.has(execution.id) &&
                <form action={correctReportedTrade}>
                  <References locale={locale} leagueId={leagueId} competitionId={competitionId}/>
                  <input type="hidden" name="execution_id" value={execution.id}/>
                  <button className="danger-button" type="submit">{text.correctTrade}</button>
                </form>}
            </div>)}</div>}
      </section>
      <section className="trade-card ranking-card">
        <h4>{text.ranking}</h4>
        <ol>{ranking.rows.map(row => <li key={row.user_id}>
          <span className="rank-number">{row.rank}</span><strong>{row.display_name}</strong>
          {row.joined_late && <small>{text.joinedLateBadge}</small>}
          <span>{formatPercent(row.cumulative_return, locale)}</span>
        </li>)}</ol>
      </section>
    </div>
  </div>;
}

function References({locale, leagueId, competitionId}: {
  locale: Locale; leagueId: string; competitionId: string;
}) {
  return <><input type="hidden" name="locale" value={locale}/><input type="hidden" name="league_id" value={leagueId}/><input type="hidden" name="competition_id" value={competitionId}/></>;
}

function Metric({label, value}: {label: string; value: string}) {
  return <div><span>{label}</span><strong>{value}</strong></div>;
}

function formatPercent(value: string, locale: Locale) {
  return new Intl.NumberFormat(locale === "es" ? "es-ES" : "en-GB", {
    style: "percent", minimumFractionDigits: 2, maximumFractionDigits: 2
  }).format(Number(value));
}
