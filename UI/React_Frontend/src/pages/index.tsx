import { useEffect, useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Table, TableHeader, TableRow, TableCell, TableBody } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, LineChart, Line } from 'recharts';
import { BarChart2, LineChart as LineIcon } from 'lucide-react';

export default function QuantDashboard() {
  const [profitData, setProfitData] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchProfitData();
    const interval = setInterval(fetchProfitData, 5000);
    return () => clearInterval(interval);
  }, []);

  async function fetchProfitData() {
    setLoading(true);
    try {
      const res = await fetch('http://localhost:8000/api/profit-book');
      const data = await res.json();
      setProfitData(data.map((d: any, i: number) => ({
        ...d,
        index: i,
        filled_price: parseFloat(d.filled_price),
        qty: parseInt(d.qty, 10),
        notional: parseFloat(d.notional)
      })));
    } finally {
      setLoading(false);
    }
  }

  const pnlData = profitData.map((d, i) => ({
    name: i + 1,
    cumulative: profitData.slice(0, i + 1).reduce((acc, x) =>
      acc + x.notional * (x.action === 'BUY' ? -1 : 1), 0)
  }));
  const volumeData = profitData.map((d, i) => ({ name: i + 1, volume: d.qty }));

  return (
    <div className="p-6 grid gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold flex items-center gap-2">
          <LineIcon className="w-6 h-6" /> Quant Dashboard
        </h1>
        <Button onClick={fetchProfitData} disabled={loading}>
          Refresh
        </Button>
      </div>

      <Card>
        <CardContent>
          <h2 className="text-xl font-semibold mb-4">Live Profit Book</h2>
          <Table>
            <TableHeader>
              <TableRow>
                <TableCell>#</TableCell>
                <TableCell>Symbol</TableCell>
                <TableCell>Action</TableCell>
                <TableCell>Price</TableCell>
                <TableCell>Qty</TableCell>
                <TableCell>Notional</TableCell>
              </TableRow>
            </TableHeader>
            <TableBody>
              {profitData.map(row => (
                <TableRow key={row.index}>
                  <TableCell>{row.index + 1}</TableCell>
                  <TableCell>{row.symbol}</TableCell>
                  <TableCell>{row.action}</TableCell>
                  <TableCell>{row.filled_price.toFixed(2)}</TableCell>
                  <TableCell>{row.qty}</TableCell>
                  <TableCell>{row.notional.toFixed(2)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <CardContent>
            <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
              <LineIcon className="w-5 h-5" /> Cumulative PnL
            </h2>
            <LineChart width={400} height={250} data={pnlData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Line type="monotone" dataKey="cumulative" />
            </LineChart>
          </CardContent>
        </Card>

        <Card>
          <CardContent>
            <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
              <BarChart2 className="w-5 h-5" /> Trade Volume
            </h2>
            <BarChart width={400} height={250} data={volumeData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="volume" />
            </BarChart>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
