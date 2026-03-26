import "./globals.css";

export const metadata = {
  title: "TAT Monitor — Lab Batch Monitoring System",
  description: "Real-time Turnaround Time and Batch Monitoring Dashboard for Laboratory Diagnostics",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
