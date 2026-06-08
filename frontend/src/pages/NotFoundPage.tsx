import { Link } from "react-router-dom";
import { ShieldIcon } from "../components/icons";

export function NotFoundPage() {
  return (
    <div className="page" style={{ alignItems: "center", justifyContent: "center", flex: 1 }}>
      <div className="state-block">
        <ShieldIcon size={32} className="state-icon" />
        <div className="state-title">Page not found</div>
        <div className="state-detail">The console route you're looking for doesn't exist.</div>
        <Link to="/alerts" className="btn btn-primary btn-sm" style={{ marginTop: 8 }}>
          Back to Alert Queue
        </Link>
      </div>
    </div>
  );
}
