import { Link } from "react-router-dom";
import "./landing.css";

export default function LandingPage() {
  return (
    <div className="landing-page">
      <div className="landing-orb landing-orb-1" />
      <div className="landing-orb landing-orb-2" />
      <div className="landing-orb landing-orb-3" />

      <div className="landing-topbar-wrapper">
      <header className="landing-topbar landing-fade-up">
        <img className="landing-logo" src="/comp_ai-logo.png" alt="COMPL.AI" />
        <nav className="landing-nav">
          <a href="#demo" className="landing-nav-link">Product</a>
          <a href="#demo" className="landing-nav-link">How it works</a>
          <Link to="/app" className="landing-nav-cta">Open app</Link>
        </nav>
      </header>
      </div>

      <section className="landing-hero">
        <h1 className="landing-fade-up landing-fade-up-delay-2">
          Vendor compliance in{" "}
          <span className="landing-hero-accent">minutes</span>
        </h1>

        <p className="landing-fade-up landing-fade-up-delay-3">
          Screen any software vendor's legal surface: T&amp;Cs, DPA, DPIA, and
          ROPA — with a single URL.
        </p>

        <div className="landing-cta-group landing-fade-up landing-fade-up-delay-4">
          <Link to="/app" className="landing-cta-primary">
            Start screening — it's free
          </Link>
          <a href="#demo" className="landing-cta-secondary">
            See it in action ↓
          </a>
        </div>
      </section>

      <section id="demo" className="landing-demo landing-fade-up landing-fade-up-delay-4">
        <div className="landing-demo-frame">
          <div className="landing-demo-chrome">
            <span className="landing-demo-dot" />
            <span className="landing-demo-dot" />
            <span className="landing-demo-dot" />
            <span className="landing-demo-url">app.compl.ai/review — stripe.com</span>
          </div>
          <div className="landing-demo-body">
            <div className="landing-demo-placeholder">
              <div className="landing-demo-placeholder-icon">⚖</div>
              <p>
                Paste a vendor URL and get a ranked compliance report in under 60
                seconds — clause-level risk ratings, DPA checklist, DPIA screening,
                and an auto-generated ROPA record.
              </p>
            </div>
          </div>
          <div className="landing-demo-glow" />
        </div>
      </section>
    </div>
  );
}
