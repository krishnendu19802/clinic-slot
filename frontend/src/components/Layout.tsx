import { Link, Outlet, useNavigate } from "react-router-dom";
import { useActiveHolds } from "../api/queries";
import { useAuth } from "../auth/AuthContext";
import { useCountdown } from "../lib/useCountdown";
import { mmss } from "../lib/format";

function ResumeHold() {
  const { data } = useActiveHolds(true);
  const hold = data?.[0]; // soonest-expiring first
  const left = useCountdown(hold?.hold_expires_at, hold?.server_time);
  if (!hold || !left) return null;
  const step = hold.patient ? "payment" : "details";
  return <Link to={`/book/${hold.id}/${step}`} className="hold">Resume booking · {mmss(left)}</Link>;
}

export default function Layout() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  return (
    <>
      <nav className="nav">
        <Link to="/" className="brand">ClinicSlot</Link>
        <div className="nav-links">
          {user?.role === "doctor" ? (
            <>
              <Link to="/doctor/onboarding">Profile</Link>
              <Link to="/doctor/schedule">Schedule</Link>
            </>
          ) : (
            <>
              <Link to="/doctors">Find doctors</Link>
              {user && <Link to="/bookings">My bookings</Link>}
            </>
          )}
          {user?.role === "patient" && <ResumeHold />}
          {user ? (
            <button onClick={async () => { await signOut(); navigate("/"); }}>Log out</button>
          ) : (
            <Link to="/login" className="btn primary">Log in</Link>
          )}
        </div>
      </nav>
      <Outlet />
      <p className="footer">Not for emergencies. Call your local emergency number. ClinicSlot does not give medical advice.</p>
    </>
  );
}
