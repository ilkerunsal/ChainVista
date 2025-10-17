from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional, Tuple
import statistics
import math


app = FastAPI(title="AI Anomaly Service")

class AnomalyRequest(BaseModel):
    """
    Request payload for anomaly detection. Expects a list of numeric values
    representing a time series. The last value in the list is evaluated for
    anomaly using a z-score against the previous values. An optional
    threshold parameter can be provided to adjust sensitivity (default ±2).
    """
    values: List[float] = Field(..., description="Time series of numeric measurements")
    threshold: float = Field(2.0, description="Z-score threshold to flag anomaly")

class AnomalyResponse(BaseModel):
    """Response from anomaly detection."""
    score: float
    is_anomaly: bool
    message: str

class LabelRequest(BaseModel):
    """
    Request to classify a blockchain address. The chain name can be provided
    to allow chain-specific heuristics.
    """
    address: str
    chain: Optional[str] = None

class LabelResponse(BaseModel):
    """
    Response containing the label and a confidence score between 0 and 1.
    """
    label: str
    confidence: float
    details: Dict[str, Any]

# --- Smart Contract Analyzer Models ---
class ContractAnalysisRequest(BaseModel):
    """
    Request payload for analyzing compiled smart contract bytecode. The
    provided bytecode should be a hex-encoded string beginning with `0x`.
    The analyzer will decode the bytecode into EVM opcodes, count their
    occurrences, estimate total gas cost based on intrinsic gas costs, and
    identify patterns indicative of gas waste. The goal is to give basic
    optimization suggestions similar to static analysis tools like PeCatch.
    """
    bytecode: str = Field(..., description="Hex-encoded contract bytecode beginning with 0x")

class ContractAnalysisResponse(BaseModel):
    """
    Response containing opcode statistics, estimated gas usage, and simple
    optimization suggestions based on known gas-heavy patterns. The
    `opcode_counts` map lists the frequency of each opcode encountered.
    The `estimated_gas` provides a rough total gas cost assuming each
    opcode incurs its intrinsic gas cost. The `recommendations` field
    contains human-readable suggestions for reducing gas consumption.
    """
    opcode_counts: Dict[str, int]
    estimated_gas: float
    recommendations: List[str]

# --- MEV & Bot Detection Models ---
class TransactionInfo(BaseModel):
    """
    Minimal transaction representation used for MEV/bot detection. Fields include
    transaction hash, from/to addresses, transferred value (in wei), timestamp and
    gas price (in gwei). Timestamp should be in seconds since epoch.
    """
    tx_hash: str
    from_address: str
    to_address: str
    value: float
    timestamp: int
    gas_price: float

class MEVDetectionRequest(BaseModel):
    """
    Request payload for MEV & bot detection. Contains a list of recent
    transactions (in chronological order) that will be analysed to detect
    front‑running, sandwich attacks and liquidation patterns. The analysis
    returns a classification of potential bot type, the MEV strategy used,
    and a spam score indicating likelihood of manipulative behaviour.
    """
    transactions: List[TransactionInfo]

class MEVDetectionResponse(BaseModel):
    """
    Response for MEV & bot detection. Contains classification results for
    detected suspicious patterns. If no suspicious pattern is found, the
    bot_type and mev_strategy will be "none", and spam_score will be low.
    """
    bot_type: str
    mev_strategy: str
    spam_score: float
    details: Dict[str, Any]

# --- Liquidity & Bridge Flow Models ---
class LiquidityEvent(BaseModel):
    """
    Represents a staking, unstaking or bridging event used for liquidity and
    bridge flow analysis. `protocol` identifies the DeFi protocol or bridge
    involved. `chain_from` and `chain_to` denote the source and destination
    chains (for staking events they may be the same). `token` is the asset
    symbol, and `amount` is the quantity transferred. `event_type` must be
    one of 'stake', 'unstake', 'bridge_out', or 'bridge_in'. The timestamp
    indicates when the event occurred (seconds since epoch).
    """
    protocol: str
    chain_from: str
    chain_to: str
    token: str
    amount: float
    event_type: str
    timestamp: int

class LiquidityBridgeRequest(BaseModel):
    """
    Request payload for liquidity and bridge flow analysis. Contains a list
    of staking/unstaking or bridging events. The analysis computes total
    value locked (TVL) per protocol and summarizes cross‑chain flows by
    aggregating bridge events.
    """
    events: List[LiquidityEvent]

class LiquidityBridgeResponse(BaseModel):
    """
    Response containing aggregated TVL per protocol and summary of cross‑chain
    flows. `tvl_by_protocol` maps protocol names to their current net
    balance (stakes minus unstakes). `bridge_flows` is a list of objects
    summarizing flows between pairs of chains for each protocol.
    """
    tvl_by_protocol: Dict[str, float]
    bridge_flows: List[Dict[str, Any]]

# --- Governance Activity Prediction Models ---
class ParticipantFeatures(BaseModel):
    """
    Features describing a DAO participant for governance activity prediction.
    `address` is the participant's wallet or delegate address. `votes_count`
    is the number of votes they cast in past proposals, `proposals_count`
    is the number of proposals they created, and `delegations_count` is the
    number of times they delegated or changed delegation. These counts
    form the input features for a simple logistic regression model.
    """
    address: str
    votes_count: int
    proposals_count: int
    delegations_count: int

class GovernancePredictRequest(BaseModel):
    """
    Request payload for governance activity prediction. Contains a list of
    participants with their feature counts. The model predicts the probability
    that each participant will be active in upcoming proposals based on
    logistic regression coefficients.
    """
    participants: List[ParticipantFeatures]
    top_n: Optional[int] = Field(None, description="Return only the top N participants by predicted probability")

class ParticipantPrediction(BaseModel):
    """
    Individual prediction result for a participant, including their address,
    predicted probability of activity and the raw score from the logistic
    function. The raw score is useful for debugging or tuning coefficients.
    """
    address: str
    probability: float
    score: float

class GovernancePredictResponse(BaseModel):
    """
    Response containing predictions for all provided participants. If top_n
    was specified in the request, only the highest probability participants
    are returned. The predictions are sorted in descending order of probability.
    """
    predictions: List[ParticipantPrediction]

def predict_governance_activity(participants: List[ParticipantFeatures], top_n: Optional[int] = None) -> GovernancePredictResponse:
    """
    Predict which DAO participants are likely to be active in future votes.
    Uses a simple logistic regression model with manually chosen coefficients.
    The model computes a linear score from the feature counts and applies
    the logistic sigmoid function to map to a probability between 0 and 1.
    """
    # Define model coefficients. In a production system these would be
    # learned from historical data. Here we choose values that weight
    # proposals more heavily than votes, reflecting that proposers tend to be
    # more engaged. Delegations have a smaller positive contribution.
    intercept = -1.0
    coef_votes = 0.2
    coef_proposals = 0.5
    coef_delegations = 0.1
    preds: List[ParticipantPrediction] = []
    for p in participants:
        score = intercept + coef_votes * p.votes_count + coef_proposals * p.proposals_count + coef_delegations * p.delegations_count
        # Use math.exp for better precision when computing the logistic sigmoid instead of a hard-coded base.
        probability = 1.0 / (1.0 + math.exp(-score))
        preds.append(ParticipantPrediction(address=p.address, probability=probability, score=score))
    # Sort descending by probability
    preds.sort(key=lambda x: x.probability, reverse=True)
    if top_n is not None:
        preds = preds[:top_n]
    return GovernancePredictResponse(predictions=preds)


@app.post("/predict_governance_activity", response_model=GovernancePredictResponse)
def predict_governance_activity_endpoint(req: GovernancePredictRequest) -> GovernancePredictResponse:
    """
    Predict the probability that DAO participants will be active in future
    governance decisions. Accepts a list of participants with feature
    counts (votes_count, proposals_count, delegations_count) and returns
    logistic regression predictions. Optionally, return only the top N
    participants with the highest predicted probabilities.
    """
    return predict_governance_activity(req.participants, req.top_n)

# --- Exploit & Flash Loan Detection Models ---
class FlashLoanEvent(BaseModel):
    """
    Represents a borrow or repay event associated with a flash loan. The
    `event_type` must be 'borrow' or 'repay'. The `amount` is the loan
    principal or repayment amount (in token units), `timestamp` is seconds
    since epoch, and `token` identifies the asset involved. For more
    complete analysis additional fields such as transaction fee could be
    included, but this simplified model focuses on temporal patterns.
    """
    tx_hash: str
    event_type: str
    amount: float
    timestamp: int
    token: str

class FlashLoanDetectionRequest(BaseModel):
    """
    Request payload for flash loan and exploit detection. Contains a list
    of flash loan events (borrow and repay). The events should be ordered by
    occurrence time to enable temporal analysis.
    """
    events: List[FlashLoanEvent]

class FlashLoanDetectionResponse(BaseModel):
    """
    Response indicating whether an exploit or suspicious flash loan pattern
    was detected. The flag `exploit_suspect` is true if the heuristic
    analysis finds an abnormal borrow/repay pattern. Additional details
    provide context for the decision.
    """
    exploit_suspect: bool
    details: Dict[str, Any]

def detect_flash_loan(events: List[FlashLoanEvent]) -> FlashLoanDetectionResponse:
    """
    Detect potential exploit patterns involving flash loans. The heuristic
    checks for large borrow events followed by immediate repayment in the
    same or near block (short time window) without intermediate value-adding
    operations. Such patterns may indicate misuse like price manipulation.
    """
    if not events or len(events) < 2:
        return FlashLoanDetectionResponse(exploit_suspect=False, details={"reason": "not enough events"})
    # Sort by timestamp ascending
    evs = sorted(events, key=lambda e: e.timestamp)
    # Compute average amount to identify unusually large loans
    amounts = [e.amount for e in evs if e.event_type == 'borrow']
    avg_amount = sum(amounts) / len(amounts) if amounts else 0.0
    for i in range(len(evs) - 1):
        a = evs[i]
        b = evs[i + 1]
        # Check for a borrow immediately followed by a repay on same token
        if a.event_type == 'borrow' and b.event_type == 'repay' and a.token == b.token:
            time_delta = b.timestamp - a.timestamp
            # If repayment occurs within 30 seconds and loan amount is abnormally high
            if time_delta < 30 and a.amount > avg_amount * 2:
                return FlashLoanDetectionResponse(
                    exploit_suspect=True,
                    details={
                        "borrow_tx": a.tx_hash,
                        "repay_tx": b.tx_hash,
                        "amount": a.amount,
                        "avg_borrow_amount": avg_amount,
                        "time_delta": time_delta
                    }
                )
    return FlashLoanDetectionResponse(exploit_suspect=False, details={})


@app.post("/detect_flash_loan", response_model=FlashLoanDetectionResponse)
def detect_flash_loan_endpoint(req: FlashLoanDetectionRequest) -> FlashLoanDetectionResponse:
    """
    Identify suspicious flash loan patterns that could indicate an exploit or
    flash loan attack. Accepts a sequence of flash loan events (borrow and
    repay) and returns a flag indicating whether an exploit is suspected.
    """
    return detect_flash_loan(req.events)

# --- Predictive Analytics & Forecasting Models ---
class ForecastRequest(BaseModel):
    """
    Request payload for univariate time series forecasting. `values` is a
    list of historical observations (e.g., liquidity levels, token prices
    or transaction volumes). `horizon` specifies how many future time
    steps to predict. The forecasting method here uses a simple linear
    regression on the index of the series to extrapolate the trend. This
    approach captures linear trends but will not model seasonality or
    nonlinear patterns as sophisticated models like Prophet or LSTM would.
    """
    values: List[float]
    horizon: int = Field(1, description="Number of future values to forecast")

class ForecastResponse(BaseModel):
    """
    Response containing the predicted values for the specified horizon and
    the coefficients of the fitted linear regression (slope and intercept).
    The predictions are ordered sequentially from the next time step to
    horizon steps ahead.
    """
    predictions: List[float]
    slope: float
    intercept: float

def forecast_time_series(values: List[float], horizon: int) -> ForecastResponse:
    """
    Perform a simple linear regression on a time series and extrapolate
    future values. The time index is assumed to be equally spaced and
    starting from 0. Returns the predicted values along with slope and
    intercept of the fitted line. If fewer than 2 observations are
    provided, the function returns the last observed value repeated.
    """
    n = len(values)
    if n < 2:
        # Not enough data to fit a line; repeat last value
        last_val = values[-1] if values else 0.0
        return ForecastResponse(predictions=[last_val] * horizon, slope=0.0, intercept=last_val)
    # Fit linear regression y = m*x + b using least squares
    xs = list(range(n))
    ys = values
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((xs[i] - mean_x) * (ys[i] - mean_y) for i in range(n))
    den = sum((xs[i] - mean_x) ** 2 for i in range(n)) or 1e-8
    slope = num / den
    intercept = mean_y - slope * mean_x
    predictions: List[float] = []
    for t in range(n, n + horizon):
        predictions.append(slope * t + intercept)
    return ForecastResponse(predictions=predictions, slope=slope, intercept=intercept)


@app.post("/forecast_series", response_model=ForecastResponse)
def forecast_series_endpoint(req: ForecastRequest) -> ForecastResponse:
    """
    Forecast future values of a univariate time series using simple linear
    regression. Accepts the historical `values` and a `horizon` indicating
    how many future points to predict. Returns predicted values and the
    regression coefficients.
    """
    return forecast_time_series(req.values, req.horizon)

# --- ZK-Analytics (Privacy Layer) Models ---
class PrivateQueryRequest(BaseModel):
    """
    Request for a privacy-preserving analytics query. The `values` field
    contains sensitive numeric data which the client wishes to analyze
    without revealing the raw values. The `query` specifies the type of
    aggregate computation to perform (e.g., 'sum', 'avg', 'count'). Only
    simple aggregates are supported in this demonstration.
    """
    values: List[float]
    query: str

class PrivateQueryResponse(BaseModel):
    """
    Response for a privacy-preserving query. Returns the result of the
    aggregate computation and a placeholder zero-knowledge proof string
    indicating that the computation was performed correctly without
    disclosing individual inputs. In a real implementation, the proof would
    be a ZK-SNARK or similar cryptographic artifact.
    """
    result: float
    zk_proof: str

def perform_private_query(values: List[float], query: str) -> PrivateQueryResponse:
    """
    Perform a simple aggregate computation on a list of values without
    revealing individual elements. Supports 'sum', 'avg', and 'count'. The
    returned zk_proof is a dummy string for demonstration purposes. In a
    production system, this would generate a real zero-knowledge proof.
    """
    q = query.lower()
    if not values:
        return PrivateQueryResponse(result=0.0, zk_proof="zkproof-placeholder")
    if q == 'sum':
        res = sum(values)
    elif q == 'avg' or q == 'mean':
        res = sum(values) / len(values)
    elif q == 'count':
        res = float(len(values))
    else:
        # Unsupported query
        res = 0.0
    return PrivateQueryResponse(result=res, zk_proof="zkproof-placeholder")


@app.post("/private_query", response_model=PrivateQueryResponse)
def private_query_endpoint(req: PrivateQueryRequest) -> PrivateQueryResponse:
    """
    Perform a privacy-preserving aggregate query over sensitive numeric
    values. Currently supports sum, average and count. Returns the result
    and a dummy zero-knowledge proof string indicating that the computation
    was executed without exposing individual values.
    """
    return perform_private_query(req.values, req.query)

# --- NFT Collection Analytics Models ---
class NFTStatsRequest(BaseModel):
    """
    Request payload for NFT collection analytics. Takes a collection contract
    address and optionally the chain name. The service returns basic
    statistics about the collection including total supply, number of
    unique owners, a history of floor prices and a wash trade score.
    """
    collection_address: str
    chain: Optional[str] = None

class NFTStatsResponse(BaseModel):
    """
    Response containing NFT collection statistics. The `floor_price_history`
    is a list of historical floor prices (e.g., daily or weekly) from
    earliest to latest. The `wash_trade_score` is a value between 0 and 1
    indicating the likelihood of wash trading in the collection, where
    higher scores represent higher likelihood of wash trades.
    """
    total_supply: int
    num_owners: int
    floor_price_history: List[float]
    wash_trade_score: float

def get_nft_collection_stats(collection_address: str, chain: Optional[str] = None) -> NFTStatsResponse:
    """
    Retrieve NFT collection statistics. In a production system this would
    query an NFT indexing service or blockchain data. Here we return
    simulated values. The wash_trade_score is randomly generated for
    demonstration purposes.
    """
    # Simulate some metrics based on the address hash. Use a local random
    # generator seeded deterministically on the address to avoid altering
    # global random state and to produce repeatable results for the same
    # address. This ensures that calls to this function do not affect
    # randomness used elsewhere in the application.
    import random
    rand = random.Random(hash(collection_address) % 10**8)
    total_supply = rand.randint(1000, 10000)
    num_owners = rand.randint(total_supply // 2, total_supply)
    floor_price_history = [round(rand.uniform(0.1, 2.0), 2) for _ in range(10)]
    wash_trade_score = round(rand.uniform(0.0, 1.0), 2)
    return NFTStatsResponse(
        total_supply=total_supply,
        num_owners=num_owners,
        floor_price_history=floor_price_history,
        wash_trade_score=wash_trade_score
    )


@app.post("/nft_stats", response_model=NFTStatsResponse)
def nft_stats(req: NFTStatsRequest) -> NFTStatsResponse:
    """
    Get analytics for an NFT collection. Returns total supply, number of
    unique owners, a floor price history and a wash trade likelihood score.
    """
    return get_nft_collection_stats(req.collection_address, req.chain)

# --- Compliance & Risk Dashboard Models ---
class RiskScoreRequest(BaseModel):
    """
    Request payload for compliance risk scores. Contains a list of
    addresses to evaluate. In a real system, these would be looked up in
    services like Chainalysis, TRM Labs or Elliptic. Here we generate
    synthetic risk scores and attributes.
    """
    addresses: List[str]

class AddressRisk(BaseModel):
    address: str
    risk_score: float
    country: str
    origin: str
    sanction_flag: bool

class RiskScoreResponse(BaseModel):
    """
    Response containing risk information for a list of addresses. Each
    address has a risk score between 0 and 1 (higher is riskier), a
    country of origin, an origin description and whether the address is
    sanctioned.
    """
    risks: List[AddressRisk]

def get_risk_scores(addresses: List[str]) -> RiskScoreResponse:
    """
    Generate synthetic compliance risk scores for a list of addresses.
    In practice this would call out to compliance APIs. Risk score and
    sanctions are randomly assigned for demonstration. Countries and
    origins are selected from a small list.
    """
    import random
    countries = ['US', 'GB', 'DE', 'TR', 'CN', 'SG']
    origins = ['exchange', 'defi_user', 'miner', 'bridge', 'mixer']
    risks: List[AddressRisk] = []
    for addr in addresses:
        # Use a deterministic local random generator per address to avoid
        # resetting the global seed on each iteration, which would affect
        # randomness globally. Seeding the RNG with a hash of the address
        # produces stable results across runs without impacting other calls.
        rand = random.Random(hash(addr) % 10**8)
        risk_score = round(rand.uniform(0.0, 1.0), 2)
        country = rand.choice(countries)
        origin = rand.choice(origins)
        sanction_flag = rand.random() < 0.05  # 5% chance of being sanctioned
        risks.append(AddressRisk(address=addr, risk_score=risk_score, country=country, origin=origin, sanction_flag=sanction_flag))
    return RiskScoreResponse(risks=risks)


@app.post("/risk_scores", response_model=RiskScoreResponse)
def risk_scores(req: RiskScoreRequest) -> RiskScoreResponse:
    """
    Generate compliance risk information for a list of addresses. Returns
    synthetic risk scores, countries of origin, origins and sanction
    statuses. In a production environment this would query compliance
    providers.
    """
    return get_risk_scores(req.addresses)

def analyze_liquidity_bridge(events: List[LiquidityEvent]) -> LiquidityBridgeResponse:
    """
    Analyze liquidity and bridge events to compute total value locked (TVL)
    by protocol and cross‑chain asset flows. Stake events increase TVL,
    unstake events decrease it. Bridge out events decrease TVL on the
    originating chain and bridge in events increase TVL on the destination
    chain. This simplified analysis treats each protocol independently.
    """
    tvl_by_protocol: Dict[str, float] = {}
    bridge_map: Dict[Tuple[str, str, str], float] = {}
    for ev in events:
        protocol = ev.protocol
        tvl_by_protocol[protocol] = tvl_by_protocol.get(protocol, 0.0)
        if ev.event_type == 'stake':
            tvl_by_protocol[protocol] += ev.amount
        elif ev.event_type == 'unstake':
            tvl_by_protocol[protocol] -= ev.amount
        elif ev.event_type == 'bridge_out':
            # decrease TVL from source chain
            tvl_by_protocol[protocol] -= ev.amount
            key = (protocol, ev.chain_from, ev.chain_to)
            bridge_map[key] = bridge_map.get(key, 0.0) + ev.amount
        elif ev.event_type == 'bridge_in':
            # increase TVL to destination chain
            tvl_by_protocol[protocol] += ev.amount
            key = (protocol, ev.chain_from, ev.chain_to)
            bridge_map[key] = bridge_map.get(key, 0.0) + ev.amount
        else:
            # unknown event type; ignore
            continue
    bridge_flows: List[Dict[str, Any]] = []
    for (protocol, from_chain, to_chain), total in bridge_map.items():
        bridge_flows.append({
            "protocol": protocol,
            "from_chain": from_chain,
            "to_chain": to_chain,
            "total_amount": total
        })
    return LiquidityBridgeResponse(tvl_by_protocol=tvl_by_protocol, bridge_flows=bridge_flows)


@app.post("/liquidity_bridge_analysis", response_model=LiquidityBridgeResponse)
def liquidity_bridge_analysis(req: LiquidityBridgeRequest) -> LiquidityBridgeResponse:
    """
    Analyze a series of staking/unstaking and bridging events to compute
    total value locked (TVL) by protocol and summarize cross‑chain flows.
    Intended for use in dashboards tracking liquidity movements and bridge
    activity across chains and protocols.
    """
    return analyze_liquidity_bridge(req.events)

def detect_mev_bot(transactions: List[TransactionInfo]) -> MEVDetectionResponse:
    """
    Perform a simple heuristic analysis on a sequence of transactions to
    detect common MEV strategies such as front‑running and sandwich attacks.
    This function is not intended as a production‑ready detector but
    demonstrates how pattern recognition might classify bot activity.
    """
    if not transactions or len(transactions) < 2:
        return MEVDetectionResponse(bot_type="none", mev_strategy="none", spam_score=0.0, details={"reason": "not enough data"})
    # Sort transactions by timestamp ascending to simplify pattern checks
    txs = sorted(transactions, key=lambda t: t.timestamp)
    bot_type = "none"
    mev_strategy = "none"
    spam_score = 0.0
    details: Dict[str, Any] = {}
    # Detect sandwich pattern: A user (same from_address) swaps, then bot quickly swaps before second user tx
    for i in range(len(txs) - 2):
        a = txs[i]
        b = txs[i + 1]
        c = txs[i + 2]
        # Sandwich: a and c have same from_address and to_address, b is from different address
        if a.from_address.lower() == c.from_address.lower() and a.to_address.lower() == c.to_address.lower() and b.from_address.lower() != a.from_address.lower():
            # Check time difference small and gas price of b high indicating front run
            if b.timestamp - a.timestamp < 30 and b.gas_price > a.gas_price:
                bot_type = "arbitrage_bot"
                mev_strategy = "sandwich"
                spam_score = 0.9
                details = {
                    "sandwich_indexes": [i, i + 1, i + 2],
                    "bot_address": b.from_address,
                    "victim_address": a.from_address
                }
                break
    # Detect simple front‑running: a bot transaction with very high gas price inserted right before victim
    if spam_score == 0.0:
        for i in range(len(txs) - 1):
            victim = txs[i]
            suspect = txs[i + 1]
            if suspect.gas_price > victim.gas_price * 1.2 and suspect.timestamp - victim.timestamp < 20:
                bot_type = "sniper_bot"
                mev_strategy = "front_running"
                spam_score = 0.7
                details = {
                    "front_run_pair": [i, i + 1],
                    "bot_address": suspect.from_address,
                    "victim_address": victim.from_address
                }
                break
    # Detect liquidation bot: repeated calls to liquidation or borrow function addresses (proxy by to_address)
    if spam_score == 0.0:
        # Count transactions to same target address
        target_counts: Dict[str, int] = {}
        for tx in txs:
            target_counts[tx.to_address.lower()] = target_counts.get(tx.to_address.lower(), 0) + 1
        # If one address appears many times, treat as liquidation bot
        for addr, count in target_counts.items():
            if count >= 3:
                bot_type = "liquidation_bot"
                mev_strategy = "liquidation"
                spam_score = 0.8
                details = {
                    "target_address": addr,
                    "count": count
                }
                break
    # If still none, assign a low spam score based on gas price variance (higher variance indicates possible MEV)
    if spam_score == 0.0:
        gas_prices = [tx.gas_price for tx in txs]
        if gas_prices:
            mean_gas = sum(gas_prices) / len(gas_prices)
            variance = sum((gp - mean_gas) ** 2 for gp in gas_prices) / len(gas_prices)
            # Use a safe denominator when calculating the spam score. If the maximum gas price
            # is zero (all prices are zero), divide by one instead of zero to avoid division
            # errors. Without this guard, variance divided by zero would throw.
            max_gas = max(gas_prices)
            denominator = max_gas if max_gas != 0 else 1
            spam_score = min(variance / denominator, 0.2)
    return MEVDetectionResponse(bot_type=bot_type, mev_strategy=mev_strategy, spam_score=spam_score, details=details)


@app.post("/detect_mev", response_model=MEVDetectionResponse)
def detect_mev(req: MEVDetectionRequest) -> MEVDetectionResponse:
    """
    Endpoint to detect potential MEV (Miner Extractable Value) or bot activity
    based on a sequence of transactions. It examines transaction ordering,
    gas prices and addresses to identify heuristic patterns such as
    sandwich attacks, front‑running or liquidation bots.
    """
    return detect_mev_bot(req.transactions)

@app.get("/health")
def health() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}

@app.post("/anomaly", response_model=AnomalyResponse)
def anomaly(req: AnomalyRequest) -> AnomalyResponse:
    """
    Evaluate whether the most recent value in a time series constitutes an
    anomaly using a z-score. A z-score measures how far a data point deviates
    from the mean in units of standard deviation; large absolute values
    indicate anomalies【981795926646541†L74-L81】. A common practice is to compute the
    mean and standard deviation over a rolling window and flag values with
    |z| > threshold as anomalous【981795926646541†L117-L127】.
    """
    values = req.values
    threshold = req.threshold
    if len(values) < 2:
        return AnomalyResponse(score=0.0, is_anomaly=False, message="Not enough data")
    # Use all but last value as reference window
    window = values[:-1]
    current = values[-1]
    mean = statistics.mean(window)
    # Use population standard deviation rather than the default sample standard
    # deviation. The population variant divides by N instead of N-1 and is
    # more appropriate for comparing one new observation against a reference
    # window representing the entire known population.
    stdev = statistics.pstdev(window) if len(window) > 1 else 0.0
    if stdev == 0:
        # If there is no variation in the reference window then any deviation
        # from the mean should be treated as an anomaly. However returning
        # an infinite z‑score would result in a JSON encoding error because
        # `Infinity` is not a valid JSON number. Instead we return a
        # sentinel score of 0.0 and simply flag the anomaly based on the
        # difference from the mean. See discussion about avoiding non‑finite
        # numbers in JSON: https://docs.python.org/3/library/json.html#infinite-and-nan-number-values
        is_anomaly = current != mean
        score = 0.0
    else:
        score = (current - mean) / stdev
        is_anomaly = abs(score) >= threshold
    message = "Anomaly" if is_anomaly else "Normal"
    return AnomalyResponse(score=score, is_anomaly=is_anomaly, message=message)

@app.post("/label", response_model=LabelResponse)
def label(req: LabelRequest) -> LabelResponse:
    """
    Classify a blockchain address into a known category. The classification
    uses simplified heuristics inspired by industry practices. For example,
    deposit heuristics identify centralized exchange addresses by following
    deposit addresses to consolidation addresses【885203800467261†L332-L338】, and
    event-based heuristics identify smart contract protocol addresses by
    monitoring specific events emitted by protocol factory contracts【885203800467261†L344-L347】.
    In this simplified implementation, we use a small static list of known
    addresses and basic pattern matching to produce a label and confidence.
    """
    address = req.address.lower()
    chain = (req.chain or "").lower()
    # Static lists of known addresses for demonstration purposes
    known_exchanges = {
        "ethereum": [
            "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"  # placeholder exchange address
        ],
        "polygon": [
            "0xdddddddddddddddddddddddddddddddddddddddd"  # placeholder exchange address on polygon
        ]
    }
    known_dex_routers = {
        "ethereum": [
            "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"  # placeholder Uniswap router address
        ],
        "polygon": [
            "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"  # placeholder QuickSwap router
        ]
    }
    known_bridges = {
        "ethereum": [
            "0xcccccccccccccccccccccccccccccccccccccccc"  # placeholder bridge address
        ],
        "polygon": []
    }
    # Determine label based on known lists
    label = "unknown"
    confidence = 0.5  # baseline confidence for unknown
    if chain in known_exchanges and address in known_exchanges[chain]:
        label = "exchange"
        confidence = 0.95
    elif chain in known_dex_routers and address in known_dex_routers[chain]:
        label = "dex_router"
        confidence = 0.9
    elif chain in known_bridges and address in known_bridges[chain]:
        label = "bridge"
        confidence = 0.9
    else:
        # Basic heuristic: addresses that interact with many unique addresses could be a service
        # In absence of on-chain data here, use simple pattern: if address is all zeros, treat as null address
        if address == "0x0000000000000000000000000000000000000000":
            label = "null_address"
            confidence = 1.0
        # If address ends with repeated digits, guess it's a contract (placeholder heuristic)
        elif address[-4:] == address[-1] * 4:
            label = "contract"
            confidence = 0.6
        else:
            label = "user"
            confidence = 0.6
    details = {
        "chain": chain,
        "address": address,
    }
    return LabelResponse(label=label, confidence=confidence, details=details)

# Opcode gas cost table (simplified). Gas costs are based on Ethereum
# Istanbul fork for cold SLOAD and SSTORE operations. Only a subset of
# opcodes is included for brevity; unlisted opcodes are assumed to cost 3 gas.
INTRINSIC_GAS_COSTS = {
    'STOP': 0,
    'ADD': 3, 'MUL': 5, 'SUB': 3, 'DIV': 5, 'SDIV': 5, 'MOD': 5, 'SMOD': 5,
    'EXP': 50, 'SIGNEXTEND': 5,
    'LT': 3, 'GT': 3, 'SLT': 3, 'SGT': 3, 'EQ': 3, 'ISZERO': 3, 'AND': 3,
    'OR': 3, 'XOR': 3, 'BYTE': 3, 'SHL': 3, 'SHR': 3, 'SAR': 3,
    'KECCAK256': 30,
    'POP': 2,
    'MLOAD': 3, 'MSTORE': 3, 'MSTORE8': 3, 'SLOAD': 100, 'SSTORE': 20000,
    'JUMP': 8, 'JUMPI': 10,
    'PC': 2, 'MSIZE': 2, 'GAS': 2, 'JUMPDEST': 1,
    'CALL': 700, 'CALLCODE': 700, 'DELEGATECALL': 700, 'STATICCALL': 700,
    'LOG0': 375, 'LOG1': 750, 'LOG2': 1125, 'LOG3': 1500, 'LOG4': 1875,
    'CREATE': 32000, 'CREATE2': 32000,
    'RETURN': 0, 'REVERT': 0, 'INVALID': 0, 'SELFDESTRUCT': 5000
}

def decode_evm_bytecode(bytecode: str) -> List[str]:
    """
    Decode a hex-encoded EVM bytecode string into a list of opcode names.
    Opcodes that take immediate data (PUSHn) consume the appropriate number
    of bytes; these immediate bytes are skipped. Unknown opcodes are
    represented as 'UNKNOWN'. See Ethereum Yellow Paper for opcode details.
    """
    # Remove 0x prefix if present
    code = bytecode[2:] if bytecode.startswith("0x") else bytecode
    # Convert to list of bytes
    bytes_seq = [code[i:i+2] for i in range(0, len(code), 2)]
    opcodes: List[str] = []
    i = 0
    while i < len(bytes_seq):
        byte_val = int(bytes_seq[i], 16)
        # PUSH1 .. PUSH32 opcodes (0x60 to 0x7f)
        if 0x60 <= byte_val <= 0x7f:
            push_size = byte_val - 0x5f
            opcodes.append(f'PUSH{push_size}')
            i += 1 + push_size  # skip immediate bytes
            continue
        # DUP1 .. DUP16 (0x80 to 0x8f)
        if 0x80 <= byte_val <= 0x8f:
            opcodes.append(f'DUP{byte_val - 0x7f}')
            i += 1
            continue
        # SWAP1 .. SWAP16 (0x90 to 0x9f)
        if 0x90 <= byte_val <= 0x9f:
            opcodes.append(f'SWAP{byte_val - 0x8f}')
            i += 1
            continue
        # Log opcodes
        if 0xa0 <= byte_val <= 0xa4:
            opcodes.append(f'LOG{byte_val - 0xa0}')
            i += 1
            continue
        # Basic mapping for known opcodes
        OPCODE_MAP = {
            0x00: 'STOP', 0x01: 'ADD', 0x02: 'MUL', 0x03: 'SUB', 0x04: 'DIV',
            0x05: 'SDIV', 0x06: 'MOD', 0x07: 'SMOD', 0x08: 'ADDMOD',
            0x09: 'MULMOD', 0x0a: 'EXP', 0x0b: 'SIGNEXTEND',
            0x10: 'LT', 0x11: 'GT', 0x12: 'SLT', 0x13: 'SGT', 0x14: 'EQ',
            0x15: 'ISZERO', 0x16: 'AND', 0x17: 'OR', 0x18: 'XOR',
            0x19: 'BYTE', 0x1b: 'SHL', 0x1c: 'SHR', 0x1d: 'SAR',
            0x20: 'KECCAK256', 0x30: 'ADDRESS', 0x31: 'BALANCE',
            0x32: 'ORIGIN', 0x33: 'CALLER', 0x34: 'CALLVALUE',
            0x35: 'CALLDATALOAD', 0x36: 'CALLDATASIZE', 0x37: 'CALLDATACOPY',
            0x38: 'CODESIZE', 0x39: 'CODECOPY', 0x3a: 'GASPRICE',
            0x3b: 'EXTCODESIZE', 0x3c: 'EXTCODECOPY', 0x3d: 'RETURNDATASIZE',
            0x3e: 'RETURNDATACOPY', 0x3f: 'EXTCODEHASH',
            0x40: 'BLOCKHASH', 0x41: 'COINBASE', 0x42: 'TIMESTAMP',
            0x43: 'NUMBER', 0x44: 'DIFFICULTY', 0x45: 'GASLIMIT',
            0x50: 'POP', 0x51: 'MLOAD', 0x52: 'MSTORE', 0x53: 'MSTORE8',
            0x54: 'SLOAD', 0x55: 'SSTORE', 0x56: 'JUMP', 0x57: 'JUMPI',
            0x58: 'PC', 0x59: 'MSIZE', 0x5a: 'GAS', 0x5b: 'JUMPDEST',
            0xf0: 'CREATE', 0xf1: 'CALL', 0xf2: 'CALLCODE',
            0xf3: 'RETURN', 0xf4: 'DELEGATECALL', 0xf5: 'CREATE2',
            0xfa: 'STATICCALL', 0xfd: 'REVERT', 0xfe: 'INVALID',
            0xff: 'SELFDESTRUCT'
        }
        opcodes.append(OPCODE_MAP.get(byte_val, 'UNKNOWN'))
        i += 1
    return opcodes

def analyze_bytecode(bytecode: str) -> ContractAnalysisResponse:
    """
    Perform basic static analysis on EVM bytecode. Returns opcode counts,
    estimated gas, and simple optimization suggestions.
    """
    opcode_list = decode_evm_bytecode(bytecode)
    opcode_counts: Dict[str, int] = {}
    estimated_gas = 0.0
    for op in opcode_list:
        opcode_counts[op] = opcode_counts.get(op, 0) + 1
        # Add intrinsic cost if known; else assume 3 gas (typical for simple opcodes)
        estimated_gas += INTRINSIC_GAS_COSTS.get(op, 3)
    recommendations: List[str] = []
    # Heuristic suggestions
    # 1. High number of SSTORE operations indicates state writes; recommend packing storage or minimizing writes
    sstore_count = opcode_counts.get('SSTORE', 0)
    if sstore_count > 10:
        recommendations.append(
            f"Contract performs {sstore_count} SSTORE operations. Consider reducing state writes or using cheaper storage patterns."
        )
    # 2. High number of LOG instructions suggests many events; evaluate necessity
    log_ops = sum(opcode_counts.get(f'LOG{i}', 0) for i in range(5))
    if log_ops > 10:
        recommendations.append(
            f"Contract emits {log_ops} LOG events. Excessive event logging can be costly; remove unneeded events."
        )
    # 3. Calls to external contracts are expensive; count CALL/DELEGATECALL/STATICCALL
    call_ops = opcode_counts.get('CALL', 0) + opcode_counts.get('DELEGATECALL', 0) + opcode_counts.get('STATICCALL', 0)
    if call_ops > 5:
        recommendations.append(
            f"Detected {call_ops} external call operations. External calls consume extra gas; minimize calls or batch operations."
        )
    # 4. Unrecognized opcodes may indicate new EVM instructions or obfuscation; caution about compatibility
    unknown_ops = opcode_counts.get('UNKNOWN', 0)
    if unknown_ops > 0:
        recommendations.append(
            f"Found {unknown_ops} unknown opcodes. Ensure the bytecode targets the correct EVM version and avoid obfuscated code."
        )
    # Provide generic recommendation if no specific issues detected
    if not recommendations:
        recommendations.append(
            "No significant gas issues detected by heuristic analysis. Consider using a formal optimizer or auditing tool for deeper insights."
        )
    return ContractAnalysisResponse(opcode_counts=opcode_counts, estimated_gas=estimated_gas, recommendations=recommendations)


@app.post("/analyze_contract", response_model=ContractAnalysisResponse)
def analyze_contract(req: ContractAnalysisRequest) -> ContractAnalysisResponse:
    """
    Analyze an Ethereum smart contract bytecode for gas optimization. The
    analysis decodes the bytecode into opcodes, counts their occurrences,
    estimates gas consumption using intrinsic costs, and produces a set of
    heuristic recommendations to reduce gas waste. This endpoint provides
    developers with a quick assessment similar to static analyzers like
    PeCatch.
    """
    return analyze_bytecode(req.bytecode)
