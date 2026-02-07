"""
AI-Powered Threat Analysis Engine using Local Ollama
Provides intelligent threat scoring, decision-making, and natural language explanations
"""
import json
import requests
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class AIThreatEngine:
    """AI-powered threat analysis using local Ollama"""
    
    def __init__(self, model: str = "qwen2.5:14b", ollama_url: str = "http://localhost:11434"):
        self.model = model
        self.ollama_url = ollama_url
        self.api_endpoint = f"{ollama_url}/api/generate"
        
    def _call_ollama(self, prompt: str, temperature: float = 0.3) -> str:
        """Call local Ollama API"""
        try:
            response = requests.post(
                self.api_endpoint,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "temperature": temperature,
                    "stream": False
                },
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()["response"]
            else:
                logger.error(f"Ollama API error: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to call Ollama: {e}")
            return None
    
    def analyze_threat(self, process_data: Dict) -> Dict:
        """
        AI-powered threat analysis of a process
        Returns: {score: int, reasoning: str, confidence: str, recommended_action: str}
        """
        prompt = f"""You are a cybersecurity expert analyzing a process for threats.

PROCESS DATA:
- Name: {process_data.get('name', 'unknown')}
- PID: {process_data.get('pid', 'unknown')}
- CPU Usage: {process_data.get('cpu_percent', 0):.1f}%
- Memory: {process_data.get('memory_mb', 0):.1f} MB
- Command: {process_data.get('cmdline', 'N/A')[:200]}
- Parent Process: {process_data.get('parent_name', 'unknown')}
- Network Connections: {process_data.get('num_connections', 0)}
- Open Files: {process_data.get('num_open_files', 0)}
- Threads: {process_data.get('num_threads', 1)}
- User: {process_data.get('username', 'unknown')}

CONTEXT:
- System: macOS with 32GB RAM
- Protected NAS: 192.168.1.80 (contains critical data)
- Suspicious indicators: high CPU, unusual network activity, file system access patterns

Analyze this process and respond ONLY with valid JSON (no markdown, no extra text):
{{
    "threat_score": <0-100>,
    "confidence": "<high|medium|low>",
    "reasoning": "<brief explanation of why this score>",
    "threat_type": "<benign|suspicious|malware|ransomware|cryptominer|data_exfil|privilege_escalation>",
    "recommended_action": "<monitor|alert|kill|quarantine>",
    "urgency": "<low|medium|high|critical>"
}}

Consider:
1. Is this a known legitimate process?
2. Are resource usage patterns normal for this process?
3. Is the parent-child relationship suspicious?
4. Are network connections to expected destinations?
5. Could this be ransomware targeting NAS mounts?

Respond with JSON only:"""

        response = self._call_ollama(prompt, temperature=0.2)
        
        if not response:
            # Fallback to rule-based if AI fails
            return self._fallback_analysis(process_data)
        
        try:
            # Extract JSON from response (handle markdown code blocks)
            json_str = response.strip()
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()
            
            result = json.loads(json_str)
            
            # Validate structure
            required_keys = ['threat_score', 'confidence', 'reasoning', 'threat_type', 'recommended_action', 'urgency']
            if not all(k in result for k in required_keys):
                logger.warning(f"AI response missing keys: {result}")
                return self._fallback_analysis(process_data)
            
            # Store AI reasoning
            result['ai_analyzed'] = True
            result['model'] = self.model
            result['timestamp'] = datetime.now().isoformat()
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}\nResponse: {response}")
            return self._fallback_analysis(process_data)
    
    def decide_action(self, threat_data: Dict, system_context: Dict) -> Dict:
        """
        AI decides what action to take on a threat
        Returns: {action: str, reason: str, precautions: List[str]}
        """
        prompt = f"""You are an autonomous EDR security system deciding whether to take action on a potential threat.

THREAT DETAILS:
- Process: {threat_data.get('name', 'unknown')} (PID: {threat_data.get('pid', 'unknown')})
- Threat Score: {threat_data.get('threat_score', 0)}/100
- Threat Type: {threat_data.get('threat_type', 'unknown')}
- AI Reasoning: {threat_data.get('reasoning', 'N/A')}

SYSTEM CONTEXT:
- Current Time: {datetime.now().strftime('%H:%M')}
- System Health: {system_context.get('health_score', 0)}%
- Active Threats: {system_context.get('active_threats', 0)}
- User Activity: {system_context.get('user_active', False)}

DECISION FACTORS:
1. Will killing this process disrupt user workflow?
2. Is this a false positive (legitimate tool)?
3. Is immediate action required or can we monitor?
4. What's the blast radius if we're wrong?

Respond ONLY with valid JSON:
{{
    "action": "<monitor|alert_user|kill_now|quarantine|block_network>",
    "confidence": "<high|medium|low>",
    "reason": "<why this action is best>",
    "user_message": "<natural language explanation for WhatsApp alert>",
    "precautions": ["<list>", "<of>", "<precautions>"],
    "escalate": <true|false>
}}

Respond with JSON only:"""

        response = self._call_ollama(prompt, temperature=0.3)
        
        if not response:
            return self._fallback_decision(threat_data)
        
        try:
            json_str = response.strip()
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()
            
            result = json.loads(json_str)
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI decision: {e}")
            return self._fallback_decision(threat_data)
    
    def compose_alert(self, incident: Dict) -> str:
        """
        AI composes a natural language alert message
        """
        prompt = f"""You are an EDR security system writing a WhatsApp alert to the system administrator.

INCIDENT:
- Action Taken: {incident.get('action', 'unknown')}
- Process: {incident.get('process_name', 'unknown')} (PID: {incident.get('pid', 'unknown')})
- Threat Score: {incident.get('threat_score', 0)}/100
- Threat Type: {incident.get('threat_type', 'unknown')}
- Reasoning: {incident.get('reasoning', 'N/A')}

Write a clear, concise WhatsApp message (2-3 sentences) that:
1. States what action you took
2. Explains why (briefly)
3. Reassures the user or advises next steps

Tone: Professional but friendly. No jargon. No emojis unless appropriate.

Respond with ONLY the message text (no JSON, no markdown):"""

        response = self._call_ollama(prompt, temperature=0.7)
        
        if not response:
            # Fallback template
            return f"🛡️ EDR Alert: Blocked {incident.get('process_name', 'unknown process')} (threat score: {incident.get('threat_score', 0)}/100). Reason: {incident.get('reasoning', 'Suspicious behavior detected')}."
        
        return response.strip()
    
    def analyze_nas_activity(self, activity_data: Dict) -> Dict:
        """
        AI analyzes NAS access patterns for ransomware/unauthorized access
        """
        prompt = f"""You are analyzing network storage (NAS) access patterns for threats.

NAS ACTIVITY:
- Destination: {activity_data.get('nas_ip', 'unknown')}
- Process: {activity_data.get('process_name', 'unknown')}
- Files Accessed: {activity_data.get('file_count', 0)}
- Write Operations: {activity_data.get('write_ops', 0)}
- Read Operations: {activity_data.get('read_ops', 0)}
- File Types: {activity_data.get('file_types', [])}
- Access Pattern: {activity_data.get('pattern', 'unknown')}
- Time Window: {activity_data.get('time_window', 'unknown')}

RANSOMWARE INDICATORS:
- Mass file encryption (many writes, few reads)
- Accessing many file types rapidly
- Creating .encrypted, .locked extensions
- High volume in short time

Respond ONLY with valid JSON:
{{
    "is_suspicious": <true|false>,
    "threat_level": "<none|low|medium|high|critical>",
    "likely_attack": "<none|ransomware|data_theft|unauthorized_access|normal>",
    "reasoning": "<explanation>",
    "recommended_action": "<allow|monitor|block_process|unmount_nas>"
}}

Respond with JSON only:"""

        response = self._call_ollama(prompt, temperature=0.2)
        
        if not response:
            return {"is_suspicious": False, "threat_level": "none", "likely_attack": "none"}
        
        try:
            json_str = response.strip()
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()
            
            return json.loads(json_str)
            
        except json.JSONDecodeError:
            return {"is_suspicious": False, "threat_level": "none", "likely_attack": "none"}
    
    def post_incident_analysis(self, incident: Dict) -> Dict:
        """
        AI performs post-incident analysis after blocking a threat
        """
        prompt = f"""You are analyzing a security incident that was just resolved.

INCIDENT DETAILS:
- Threat: {incident.get('process_name', 'unknown')}
- Action Taken: {incident.get('action', 'unknown')}
- Threat Score: {incident.get('threat_score', 0)}/100
- Threat Type: {incident.get('threat_type', 'unknown')}
- Timeline: {incident.get('timeline', [])}

Provide a post-incident analysis. Respond ONLY with valid JSON:
{{
    "attack_vector": "<how it likely got in>",
    "attack_chain": ["<step 1>", "<step 2>", "<step 3>"],
    "data_at_risk": "<what data was threatened>",
    "lessons_learned": ["<lesson 1>", "<lesson 2>"],
    "prevention_recommendations": ["<rec 1>", "<rec 2>"],
    "similar_threats_to_watch": ["<threat 1>", "<threat 2>"]
}}

Respond with JSON only:"""

        response = self._call_ollama(prompt, temperature=0.4)
        
        if not response:
            return {"attack_vector": "unknown", "attack_chain": [], "lessons_learned": []}
        
        try:
            json_str = response.strip()
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()
            
            return json.loads(json_str)
            
        except json.JSONDecodeError:
            return {"attack_vector": "unknown", "attack_chain": [], "lessons_learned": []}
    
    def _fallback_analysis(self, process_data: Dict) -> Dict:
        """Fallback rule-based analysis if AI fails"""
        score = 0
        cpu = process_data.get('cpu_percent', 0)
        mem = process_data.get('memory_mb', 0)
        conns = process_data.get('num_connections', 0)
        
        if cpu > 80: score += 30
        elif cpu > 50: score += 15
        
        if mem > 2000: score += 20
        elif mem > 1000: score += 10
        
        if conns > 50: score += 30
        elif conns > 20: score += 15
        
        return {
            "threat_score": min(score, 100),
            "confidence": "low",
            "reasoning": "Fallback rule-based analysis (AI unavailable)",
            "threat_type": "suspicious" if score > 50 else "benign",
            "recommended_action": "alert" if score > 70 else "monitor",
            "urgency": "high" if score > 80 else "medium" if score > 50 else "low",
            "ai_analyzed": False
        }
    
    def _fallback_decision(self, threat_data: Dict) -> Dict:
        """Fallback decision if AI fails"""
        score = threat_data.get('threat_score', 0)
        
        if score >= 85:
            action = "kill_now"
        elif score >= 70:
            action = "alert_user"
        else:
            action = "monitor"
        
        return {
            "action": action,
            "confidence": "medium",
            "reason": "Fallback rule-based decision",
            "user_message": f"Threat detected: {threat_data.get('name', 'unknown')} (score: {score}/100)",
            "precautions": ["Verify manually if possible"],
            "escalate": score >= 85
        }


# Singleton instance
_ai_engine = None

def get_ai_engine(model: str = "qwen2.5:14b") -> AIThreatEngine:
    """Get or create AI engine instance"""
    global _ai_engine
    if _ai_engine is None:
        _ai_engine = AIThreatEngine(model=model)
    return _ai_engine
