interface ComingSoonPageProps {
  module: string;
}

/** Placeholder for student modules not yet implemented. */
export function ComingSoonPage({ module }: ComingSoonPageProps) {
  return (
    <div>
      <h2>{module} module coming soon</h2>
      <p>This section is not available yet.</p>
    </div>
  );
}
