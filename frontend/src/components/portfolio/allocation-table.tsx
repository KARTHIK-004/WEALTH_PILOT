import { HelpTip } from "@/components/shell/help-tip"
import { TechnicalDetails } from "@/components/shell/technical-details"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { formatPercent } from "@/lib/format"
import { getAssetDisplayName, getAssetHelp } from "@/lib/terminology"

/** Only "Investment" and "Allocation" columns — no "Role" column, since the
 * API supplies no per-asset role field and inventing one is explicitly
 * disallowed (section 10). Every row the API returned is rendered, in the
 * API's order, with its own weight formatted -- never recomputed, never
 * filtered, so an asset such as GLD can never render blank. Investments are
 * named in plain words (`lib/terminology.ts`); the tickers stay in
 * Technical details. */
export function AllocationTable({ weights }: { weights: Record<string, number> }) {
  const rows = Object.entries(weights)
  return (
    <div className="space-y-3">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Investment</TableHead>
            <TableHead className="text-right">Allocation</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map(([ticker, weight]) => {
            const help = getAssetHelp(ticker)
            return (
              <TableRow key={ticker}>
                <TableCell className="font-medium whitespace-normal">
                  <span className="inline-flex items-center gap-1">
                    {getAssetDisplayName(ticker)}
                    {help ? <HelpTip label={getAssetDisplayName(ticker)} text={help} /> : null}
                  </span>
                </TableCell>
                <TableCell className="text-right tabular-nums">{formatPercent(weight)}</TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
      <TechnicalDetails
        items={rows.map(([ticker, weight]) => ({
          label: `${getAssetDisplayName(ticker)}`,
          value: `Ticker ${ticker} · weight ${weight}`,
        }))}
      />
    </div>
  )
}
