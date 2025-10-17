import * as dotenv from 'dotenv';
import { JsonRpcProvider, Contract } from 'ethers';
import * as fs from 'fs';
import * as path from 'path';

/**
 * Analyze a transaction by tracing its execution to gather gas usage and
 * opcode distribution. This function first attempts to call the
 * `debug_traceTransaction` RPC method, which is supported by geth and
 * compatible Ethereum clients. If that fails (e.g. on public providers
 * without debug endpoints), it falls back to retrieving the transaction
 * receipt and uses the `gasUsed` from the receipt. The returned object
 * includes:
 *   - gasUsed: total gas used by the transaction (undefined if unavailable)
 *   - opcodeDensity: a frequency map of opcodes encountered during the
 *     execution trace (empty if no trace available)
 *   - gasSavingOpportunities: a simple ratio of expensive operations to
 *     total operations, which can be used as a proxy for gas waste
 */
async function analyzeTransaction(
  provider: JsonRpcProvider,
  txHash: string
): Promise<{ gasUsed?: number; opcodeDensity: Record<string, number>; gasSavingOpportunities: number }> {
  // Attempt to fetch a full execution trace. We wrap in a try/catch because
  // many providers (e.g. Infura, public RPC endpoints) do not expose
  // `debug_traceTransaction` and will throw an error. The second argument
  // specifies an empty options object to request the default tracer.
  let structLogs: any[] | undefined;
  try {
    const traceResult: any = await provider.send('debug_traceTransaction', [txHash, {}]);
    // Some clients return { structLogs: [...] }, others return the array directly.
    if (traceResult && Array.isArray(traceResult.structLogs)) {
      structLogs = traceResult.structLogs;
    } else if (Array.isArray(traceResult)) {
      structLogs = traceResult;
    }
  } catch (err) {
    // swallow error; we will fallback to receipt below
  }
  let gasUsed: number | undefined;
  const opcodeDensity: Record<string, number> = {};
  if (structLogs) {
    // Walk through the execution trace, accumulating the gas cost and opcode counts.
    let totalGasCost = 0;
    for (const step of structLogs) {
      const op = step.op as string;
      if (op) {
        opcodeDensity[op] = (opcodeDensity[op] || 0) + 1;
      }
      // Some clients provide `gasCost` per step; accumulate if present
      if (typeof step.gasCost === 'number') {
        totalGasCost += step.gasCost;
      }
    }
    gasUsed = totalGasCost;
  } else {
    // Without a trace, fall back to the transaction receipt to get the total gas used
    const receipt = await provider.getTransactionReceipt(txHash);
    if (receipt && receipt.gasUsed) {
      try {
        gasUsed = (receipt.gasUsed as any).toNumber?.() ?? parseInt(receipt.gasUsed.toString());
      } catch {
        gasUsed = Number(receipt.gasUsed);
      }
    }
  }
  // Compute a naive gas waste metric: ratio of expensive operations to total operations
  const expensiveOps = ['SSTORE', 'SLOAD', 'CALL', 'CREATE', 'LOG0', 'LOG1', 'LOG2', 'LOG3', 'LOG4'];
  let expensiveCount = 0;
  let totalOps = 0;
  for (const [op, count] of Object.entries(opcodeDensity)) {
    totalOps += count;
    if (expensiveOps.includes(op)) {
      expensiveCount += count;
    }
  }
  const gasSavingOpportunities = totalOps > 0 ? expensiveCount / totalOps : 0;
  return { gasUsed, opcodeDensity, gasSavingOpportunities };
}

/**
 * Simple in-memory aggregator for DAO governance events. It tracks the
 * number of proposals, votes and delegation changes per chain and contract.
 * A production implementation would persist these counts into a database
 * for long-term analysis and could expose them via an API endpoint.
 */
interface GovernanceStats {
  proposals: Record<string, number>;
  votes: Record<string, number>;
  delegations: Record<string, number>;
}

const governanceStats: GovernanceStats = {
  proposals: {},
  votes: {},
  delegations: {}
};

/**
 * In-memory collector for security-related events. This tracks how many
 * times each risk category occurs on each chain and contract. Categories
 * include reentrancy, overflow, denial-of-service and oracle manipulation.
 */
const securityEvents: Record<string, Record<string, number>> = {};

/**
 * Heuristic function to determine whether a given address is considered
 * labelled. In a full implementation this would consult a label database or
 * AI model. Here, we use a deterministic hash of the address to assign
 * approximately one third of addresses as labelled. This allows us to
 * demonstrate label coverage metrics without external dependencies.
 */
function isLabelledAddress(addr: string): boolean {
  // Remove 0x prefix and compute sum of character codes
  const hex = addr.slice(2).toLowerCase();
  let sum = 0;
  for (let i = 0; i < hex.length; i++) {
    sum += hex.charCodeAt(i);
  }
  // Label if sum modulo 3 equals zero
  return sum % 3 === 0;
}

/**
 * Update the security events map if the event is a known risk pattern. In
 * a real implementation, the indexer would detect these patterns by
 * scanning bytecode or decoding low-level call data. Here we assume that
 * the event name itself corresponds to a risk category (e.g., 'Reentrancy',
 * 'Overflow', 'DoS', 'OracleManipulation').
 */
function updateSecurityEvents(logInfo: any) {
  const eventName = (logInfo.event || '').toString();
  const riskCategories = ['Reentrancy', 'Overflow', 'DoS', 'OracleManipulation'];
  if (riskCategories.includes(eventName)) {
    const key = `${logInfo.chain}:${logInfo.contract}`;
    if (!securityEvents[key]) {
      securityEvents[key] = {};
    }
    securityEvents[key][eventName] = (securityEvents[key][eventName] || 0) + 1;
  }
}

/**
 * Data quality metrics state. Tracks total events processed, successfully
 * decoded events, and the last processed block per chain for ingestion lag
 * measurement. In a real implementation, you would also track the number
 * of addresses with labels to compute label coverage.
 */
const dataQualityStats: {
  totalEvents: number;
  decodedEvents: number;
  lastProcessedBlock: Record<string, number>;
  // Count of addresses encountered in event logs. Used to compute label coverage.
  totalAddresses: number;
  // Count of addresses considered labelled according to a heuristic. In a
  // production implementation this would query a label database or service.
  labelledAddresses: number;
} = {
  totalEvents: 0,
  decodedEvents: 0,
  lastProcessedBlock: {}
  , totalAddresses: 0
  , labelledAddresses: 0
};

async function reportDataQuality(chainName: string, provider: JsonRpcProvider, currentBlockNumber: number) {
  try {
    const head = await provider.getBlockNumber();
    const lastProcessed = dataQualityStats.lastProcessedBlock[chainName] || currentBlockNumber;
    const ingestLag = head - lastProcessed;
    const decodeCoverage = dataQualityStats.totalEvents > 0 ? dataQualityStats.decodedEvents / dataQualityStats.totalEvents : 0;
    const labelCoverage = dataQualityStats.totalAddresses > 0 ? dataQualityStats.labelledAddresses / dataQualityStats.totalAddresses : 0;
    const metrics = {
      type: 'data_quality',
      chain: chainName,
      ingestLag,
      decodeCoverage,
      labelCoverage
    };
    console.log(JSON.stringify(metrics));
    // Automatic error detection with simple thresholds. These thresholds can be
    // configured via environment variables or adjusted here. If ingest lag
    // grows beyond a threshold, decode coverage drops too low or label
    // coverage is poor, log an alert with a severity level. A more
    // sophisticated implementation could integrate with a monitoring system.
    const ingestLagThreshold = parseInt(process.env.INGEST_LAG_THRESHOLD || '5', 10);
    const decodeThreshold = parseFloat(process.env.DECODE_COVERAGE_THRESHOLD || '0.8');
    const labelThreshold = parseFloat(process.env.LABEL_COVERAGE_THRESHOLD || '0.5');
    if (ingestLag > ingestLagThreshold) {
      const level = ingestLag > ingestLagThreshold * 2 ? 'critical' : 'warning';
      console.log(JSON.stringify({ type: 'data_quality_alert', chain: chainName, level, message: `Ingest lag ${ingestLag} exceeds threshold ${ingestLagThreshold}` }));
    }
    if (decodeCoverage < decodeThreshold) {
      const level = decodeCoverage < decodeThreshold / 2 ? 'critical' : 'warning';
      console.log(JSON.stringify({ type: 'data_quality_alert', chain: chainName, level, message: `Decode coverage ${decodeCoverage.toFixed(2)} below threshold ${decodeThreshold}` }));
    }
    if (labelCoverage < labelThreshold) {
      const level = labelCoverage < labelThreshold / 2 ? 'critical' : 'warning';
      console.log(JSON.stringify({ type: 'data_quality_alert', chain: chainName, level, message: `Label coverage ${labelCoverage.toFixed(2)} below threshold ${labelThreshold}` }));
    }
  } catch (err) {
    console.warn(`Failed to report data quality for ${chainName}: ${err}`);
  }
}

/**
 * Monitor basic metrics on a Layer‑2 chain such as zkSync, StarkNet or Linea.
 * This function queries the current block number and timestamps to derive
 * approximate latency and inclusion delays. Since not all L2 networks expose
 * the same RPC methods, the metrics are heuristic and may not reflect
 * actual network performance. In a production environment you would use
 * specialized RPC calls or indexers provided by the respective teams.
 */
async function monitorL2Metrics(provider: JsonRpcProvider, chainName: string) {
  try {
    const blockNumber = await provider.getBlockNumber();
    const block = await provider.getBlock(blockNumber);
    const nowTs = Math.floor(Date.now() / 1000);
    const blockTs = (block as any)?.timestamp ?? nowTs;
    // Estimate latency as difference between current time and block timestamp
    const latency = nowTs - blockTs;
    // Inclusion delay is set to zero here as we don't have L1 reference; placeholder
    const inclusionDelay = 0;
    // Estimate blob size as the size of the block's transactions array
    const blobSize = (block as any)?.transactions?.length ?? 0;
    const metrics = {
      chain: chainName,
      l2BlockNumber: blockNumber,
      latency,
      inclusionDelay,
      blobSize
    };
    console.log(JSON.stringify({ type: 'l2_metrics', metrics }));
  } catch (err) {
    console.warn(`Failed to fetch L2 metrics for ${chainName}: ${err}`);
  }
}

/**
 * Update the governance statistics aggregator based on a logged event. The
 * event is expected to include at least chain, contract and event name.
 */
function updateGovernanceStats(logInfo: any) {
  const key = `${logInfo.chain}:${logInfo.contract}`;
  const eventName = (logInfo.event || '').toString();
  if (eventName === 'ProposalCreated') {
    governanceStats.proposals[key] = (governanceStats.proposals[key] || 0) + 1;
  } else if (eventName === 'VoteCast') {
    governanceStats.votes[key] = (governanceStats.votes[key] || 0) + 1;
  } else if (['DelegateChanged', 'DelegateVotesChanged', 'DelegationChanged'].includes(eventName)) {
    // Track delegation-related events. Support multiple naming conventions to avoid duplication.
    governanceStats.delegations[key] = (governanceStats.delegations[key] || 0) + 1;
  }
}

// Load environment variables. These variables should include RPC_URL_CHAIN1,
// RPC_URL_CHAIN2, etc., corresponding to the values specified in the
// configuration file. dotenv loads variables from .env at project root.
dotenv.config();

/**
 * Load the multi-chain indexer configuration. The JSON file describes an
 * array of chain definitions, each with a name, an environment variable that
 * holds the RPC URL, and a list of contracts with addresses, paths to their
 * ABI definitions, and events to listen for. This approach makes it easy to
 * extend the indexer to new chains or contracts without changing the code.
 */
function loadConfig() {
  const configPath = path.join(__dirname, '../config.json');
  const raw = fs.readFileSync(configPath, 'utf8');
  return JSON.parse(raw);
}

/**
 * Initialize event listeners for all chains and contracts defined in the
 * configuration. For each chain we create an ethers.js provider using the
 * specified RPC endpoint from an environment variable. Each contract is then
 * instantiated with its ABI, and event listeners are attached for the defined
 * event signatures. When an event fires, we log a structured JSON object
 * containing chain name, contract address, event name, arguments, transaction
 * hash, and block number. In a production indexer, you would insert these
 * records into a database table keyed by chain and contract.
 */
async function startIndexer() {
  const config = loadConfig();
  if (!config.chains || config.chains.length === 0) {
    console.error('No chains defined in config.json');
    return;
  }
  console.log('Starting multi-chain indexer...');
  for (const chainConfig of config.chains) {
    // Construct a list of RPC URLs for resilience. In addition to the primary
    // RPC environment variable (e.g. RPC_URL_CHAIN1), we look for backup
    // variables with suffixes _BACKUP1.._BACKUP5.
    const getRpcUrls = (envBase: string): string[] => {
      const urls: string[] = [];
      if (process.env[envBase]) urls.push(process.env[envBase]);
      for (let i = 1; i <= 5; i++) {
        const name = `${envBase}_BACKUP${i}`;
        if (process.env[name]) urls.push(process.env[name]!);
      }
      return urls;
    };
    const rpcUrls = getRpcUrls(chainConfig.rpcEnv);
    if (rpcUrls.length === 0) {
      console.warn(`No RPC URLs found for chain ${chainConfig.name} (env ${chainConfig.rpcEnv}). Skipping.`);
      continue;
    }
    // Attempt to find a working provider among the RPC URLs. We try each
    // provider sequentially, performing a simple getBlockNumber request to
    // ensure connectivity. The first provider that responds is used.
    let provider: JsonRpcProvider | null = null;
    for (const url of rpcUrls) {
      const prov = new JsonRpcProvider(url);
      try {
        await prov.getBlockNumber();
        provider = prov;
        console.log(`Connected to ${chainConfig.name} via ${url}`);
        break;
      } catch (err) {
        console.warn(`Failed to connect to ${chainConfig.name} via ${url}: ${err}`);
      }
    }
    if (!provider) {
      console.error(`All RPC endpoints for ${chainConfig.name} failed. Skipping chain.`);
      continue;
    }

    // If this chain is a known Layer‑2 network, collect basic metrics once.
    const layer2Names = ['zksync', 'starknet', 'linea'];
    if (layer2Names.includes(chainConfig.name.toLowerCase())) {
      monitorL2Metrics(provider, chainConfig.name).catch((err) => {
        console.warn(`Error monitoring L2 metrics for ${chainConfig.name}: ${err}`);
      });
    }
    for (const contractConfig of chainConfig.contracts) {
      const abiPath = path.join(__dirname, '../', contractConfig.abiPath);
      let abi;
      try {
        abi = JSON.parse(fs.readFileSync(abiPath, 'utf8'));
      } catch (err) {
        console.error(`Failed to load ABI for ${contractConfig.address}: ${err}`);
        continue;
      }
      const contract = new Contract(contractConfig.address, abi, provider);
      console.log(`Listening for events on ${chainConfig.name} - ${contractConfig.address}`);
      for (const eventSignature of contractConfig.events || []) {
        // Register an asynchronous listener for this event. When the event
        // fires, we capture the transaction hash and analyze the associated
        // transaction trace to extract gas usage and opcode distribution.
        contract.on(eventSignature, async (...args: any[]) => {
          const event = args[args.length - 1];
          const basicInfo = {
            chain: chainConfig.name,
            contract: contractConfig.address,
            event: (event as any).eventName || eventSignature,
            args: args.slice(0, -1),
            txHash: (event as any).transactionHash as string,
            blockNumber: (event as any).blockNumber as number
          };
          // Attempt to analyze the transaction trace. If the provider does not
          // expose a debug trace endpoint (common on public providers), we
          // fallback to using the gasUsed from the transaction receipt.
          let analysis: { gasUsed?: number; opcodeDensity: Record<string, number>; gasSavingOpportunities: number };
          try {
            analysis = await analyzeTransaction(provider, basicInfo.txHash);
          } catch (err) {
            console.warn(`Failed to analyze transaction ${basicInfo.txHash}: ${err}`);
            analysis = { gasUsed: undefined, opcodeDensity: {}, gasSavingOpportunities: 0 };
          }
          const logInfo = {
            ...basicInfo,
            traceGas: analysis.gasUsed,
            opcodeDensity: analysis.opcodeDensity,
            gasSavingOpportunities: analysis.gasSavingOpportunities
          };
          console.log(JSON.stringify(logInfo));
          // Update governance statistics if this is a governance event
          updateGovernanceStats(logInfo);
          // Update security event counts if this event matches known risk categories
          updateSecurityEvents(logInfo);
          // Update data quality metrics: increment counters and record last processed block
          dataQualityStats.totalEvents += 1;
          dataQualityStats.decodedEvents += 1; // all events in this example are decoded
          dataQualityStats.lastProcessedBlock[chainConfig.name] = logInfo.blockNumber;
          // Extract addresses from event arguments to update label coverage metrics. We
          // iterate through the arguments and identify strings that look like
          // Ethereum addresses (0x followed by 40 hex chars). Each unique
          // address is counted towards totalAddresses, and a deterministic
          // heuristic determines if it is labelled. Duplicate addresses in
          // the same event are only counted once per event.
          try {
            const seen: Set<string> = new Set();
            for (const arg of logInfo.args as any[]) {
              if (typeof arg === 'string' && /^0x[a-fA-F0-9]{40}$/.test(arg)) {
                if (!seen.has(arg)) {
                  seen.add(arg);
                  dataQualityStats.totalAddresses += 1;
                  if (isLabelledAddress(arg)) {
                    dataQualityStats.labelledAddresses += 1;
                  }
                }
              } else if (Array.isArray(arg)) {
                for (const sub of arg) {
                  if (typeof sub === 'string' && /^0x[a-fA-F0-9]{40}$/.test(sub) && !seen.has(sub)) {
                    seen.add(sub);
                    dataQualityStats.totalAddresses += 1;
                    if (isLabelledAddress(sub)) {
                      dataQualityStats.labelledAddresses += 1;
                    }
                  }
                }
              }
            }
          } catch (err) {
            console.warn(`Failed to extract addresses for label coverage: ${err}`);
          }
          // Report data quality metrics periodically or after each event (here after each event)
          reportDataQuality(chainConfig.name, provider, logInfo.blockNumber).catch(() => {});
          // TODO: Persist logInfo to database with chain and contract metadata
        });
      }
    }
  }
}

// Start the indexer and log any uncaught errors
startIndexer().catch((err) => {
  console.error(err);
});