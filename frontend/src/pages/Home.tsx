import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useSpecialities } from "../api/queries";

export default function Home() {
  const navigate = useNavigate();
  const { data: specialities = [] } = useSpecialities();
  const [city, setCity] = useState("Durgapur");
  const [speciality, setSpeciality] = useState("");
  const [date, setDate] = useState("");

  const search = (e: FormEvent) => {
    e.preventDefault();
    navigate(`/doctors?${new URLSearchParams(Object.entries({ city, speciality, date }).filter(([, v]) => v))}`);
  };

  return (
    <div className="wrap" style={{ gap: 44 }}>
      <div className="hero">
        <div>
          <span className="pill">✓ Every doctor is verified</span>
          <h1 className="big">Find the right doctor. Book a slot in two minutes.</h1>
          <p className="lead">Search local doctors by speciality, see live availability and pay securely online.</p>
          <form className="searchbar" onSubmit={search}>
            <label>Location<input value={city} onChange={(e) => setCity(e.target.value)} /></label>
            <label>Speciality
              <select value={speciality} onChange={(e) => setSpeciality(e.target.value)}>
                <option value="">Any speciality</option>
                {specialities.map((s) => <option key={s.slug} value={s.slug}>{s.name}</option>)}
              </select>
            </label>
            <label>Date<input type="date" value={date} onChange={(e) => setDate(e.target.value)} /></label>
            <button className="primary" type="submit">Search</button>
          </form>
        </div>
      </div>
      <section>
        <h2>Browse by speciality</h2>
        <div className="tiles">
          {specialities.slice(0, 8).map((s) => (
            <Link key={s.slug} to={`/doctors?speciality=${s.slug}&city=${city}`} className="card tile">
              <div className="ic">{s.name.slice(0, 2)}</div><h3>{s.name}</h3><p className="muted">{s.blurb}</p>
            </Link>
          ))}
        </div>
      </section>
      <section>
        <h2>Three steps, no phone calls</h2>
        <div className="tiles">
          <div className="card"><h3>1. Search</h3><p className="muted">Speciality and area, with live slots.</p></div>
          <div className="card"><h3>2. Pick your time</h3><p className="muted">Choose the exact slot at the clinic.</p></div>
          <div className="card"><h3>3. Pay securely</h3><p className="muted">Get your token and SMS reminders.</p></div>
        </div>
      </section>
    </div>
  );
}
