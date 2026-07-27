#!/usr/bin/env python3
"""
Live AI Recommendation Scheduler
Automatically updates AI recommendations on a schedule
"""

import schedule
import time
import subprocess
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ai_recommendations_scheduler.log'),
        logging.StreamHandler()
    ]
)

class AIRecommendationScheduler:
    """Scheduler for automatic AI recommendation updates."""
    
    def __init__(self):
        self.script_path = "generate_live_ai_simple.py"
    
    def run_ai_generation(self):
        """Run the AI recommendation generation."""
        try:
            logging.info("🤖 Starting scheduled AI recommendation generation...")
            
            result = subprocess.run(
                ["python", self.script_path],
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )
            
            if result.returncode == 0:
                logging.info("✅ AI recommendation generation completed successfully")
                # Log key metrics from output
                output_lines = result.stdout.split('\n')
                for line in output_lines:
                    if 'Generated' in line and 'recommendations' in line:
                        logging.info(f"📊 {line.strip()}")
                    elif 'Total potential savings' in line:
                        logging.info(f"💰 {line.strip()}")
            else:
                logging.error(f"❌ AI generation failed: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            logging.error("⏱️ AI generation timed out after 5 minutes")
        except Exception as e:
            logging.error(f"❌ Error running AI generation: {e}")
    
    def start_scheduler(self):
        """Start the recommendation scheduler."""
        logging.info("🚀 AI Recommendation Scheduler Starting...")
        
        # Schedule recommendations
        schedule.every().hour.do(self.run_ai_generation)  # Every hour
        schedule.every().day.at("09:00").do(self.run_ai_generation)  # Daily at 9 AM
        schedule.every().monday.at("08:00").do(self.run_ai_generation)  # Weekly on Monday
        
        logging.info("📅 Scheduled AI recommendations:")
        logging.info("   • Every hour")
        logging.info("   • Daily at 9:00 AM") 
        logging.info("   • Weekly on Monday at 8:00 AM")
        
        # Run once immediately
        logging.info("🔄 Running initial AI recommendation generation...")
        self.run_ai_generation()
        
        # Keep scheduler running
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            logging.info("🛑 Scheduler stopped by user")
        except Exception as e:
            logging.error(f"❌ Scheduler error: {e}")

def main():
    """Main function to start the scheduler."""
    scheduler = AIRecommendationScheduler()
    scheduler.start_scheduler()

if __name__ == "__main__":
    main()