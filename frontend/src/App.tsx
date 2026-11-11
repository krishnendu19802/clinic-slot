import { Route, Routes } from "react-router-dom";
import { NotFound } from "./components/bits";
import Layout from "./components/Layout";
import Bookings from "./pages/Bookings";
import Confirmed from "./pages/Confirmed";
import Details from "./pages/Details";
import DoctorProfile from "./pages/DoctorProfile";
import Home from "./pages/Home";
import Login from "./pages/Login";
import Payment from "./pages/Payment";
import Results from "./pages/Results";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="login" element={<Login />} />
        <Route path="doctors" element={<Results />} />
        <Route path="doctors/:id" element={<DoctorProfile />} />
        <Route path="book/:id/details" element={<Details />} />
        <Route path="book/:id/payment" element={<Payment />} />
        <Route path="book/:id/confirmed" element={<Confirmed />} />
        <Route path="bookings" element={<Bookings />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
