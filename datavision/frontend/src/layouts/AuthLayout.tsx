import { Outlet } from 'react-router-dom';

export default function AuthLayout() {
  return (
    <div className="dv-login-bg">
      <Outlet />
    </div>
  );
}
