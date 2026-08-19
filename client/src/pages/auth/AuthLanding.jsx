import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import AuthBrandingPanel from '../../components/auth/AuthBrandingPanel'

export default function AuthLanding() {
  return (
    <div className="min-h-screen flex">
      {/* Left Side - Gradient */}
      <AuthBrandingPanel
          heading="Welcome to CreditDataWatch!"
          subtext="Access business credit insights, manage your account, and protect your business."
        />

      {/* Right Side - Form */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-8 lg:p-12">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-[440px]">
          <div className="text-center mb-8">
            <h1 className="text-[1.8rem] font-bold text-[#0F172A] mb-2">
              Access CreditDataWatch
            </h1>
            <p className="text-[#475569]">GST-validated access. Choose how you want to continue.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            <Link 
              to="/auth/login" 
              className="group bg-white rounded-[16px] border border-[#E2E8F0] shadow-sm hover:shadow-md transition-all duration-200 p-6 text-center"
            >
              <p className="font-bold text-[#0F172A] text-lg mb-1">Login</p>
              <p className="text-sm text-[#475569]">For registered GST entities</p>
            </Link>
            <Link 
              to="/auth/register" 
              className="group bg-white rounded-[16px] border border-[#E2E8F0] shadow-sm hover:shadow-md transition-all duration-200 p-6 text-center"
            >
              <p className="font-bold text-[#0F172A] text-lg mb-1">Register</p>
              <p className="text-sm text-[#475569]">Validate GST and start</p>
            </Link>
          </div>
        </motion.div>
      </div>
    </div>
  )
}
