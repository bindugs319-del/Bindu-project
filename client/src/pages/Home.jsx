import HeroSection from '../components/home/HeroSection'
import TrustTicker from '../components/ui/TrustTicker'
import ScamAlert from '../components/home/ScamAlert'
import CreditScoreInfo from '../components/home/CreditScoreInfo'
import StatsSection from '../components/home/StatsSection'
import Testimonial from '../components/home/Testimonial'
import FAQSection from '../components/home/FAQSection'

export default function Home() {
  return (
    <>
      <HeroSection />
      <TrustTicker />
      <ScamAlert />
      <StatsSection />
      <Testimonial />
      <CreditScoreInfo />
      <FAQSection />
    </>
  )
}
