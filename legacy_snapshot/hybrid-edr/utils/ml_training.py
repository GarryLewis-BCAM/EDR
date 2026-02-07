"""
ML Training Pipeline for EDR Threat Detection
- Feature extraction from process/network events
- Auto-labeling based on suspicious scores
- Isolation Forest (unsupervised anomaly detection)
- Random Forest (supervised classification)
- Model persistence and metrics tracking
"""
import sys
import logging
import json
import pickle
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Any

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report, roc_auc_score
)


logger = logging.getLogger(__name__)


class MLTrainingPipeline:
    """Production-grade ML training pipeline for threat detection"""
    
    def __init__(self, config: Dict, db):
        """
        Initialize training pipeline
        
        Args:
            config: System configuration dict
            db: EDRDatabase instance for data access
        """
        self.config = config
        self.db = db
        
        # Get training config
        self.ml_config = config.get('ml_models', {})
        self.training_config = self.ml_config.get('training', {})
        
        # Set paths
        self.models_dir = Path(config['paths']['models'])
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        self.metrics_dir = self.models_dir.parent / 'metrics'
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        
        # Models
        self.isolation_forest = None
        self.random_forest = None
        self.scaler = None
        
        # Training results
        self.metrics = {}
        self.feature_names = []
        
    def extract_features(self, limit: int = None) -> pd.DataFrame:
        """
        Extract feature vectors from process events
        
        Returns DataFrame with columns:
        - cpu_percent: CPU usage
        - memory_mb: Memory usage in MB
        - num_threads: Thread count
        - connections_count: Number of network connections
        - suspicious_score: Current threat score
        - parent_pid_norm: Normalized parent PID (0 if no parent)
        - has_network: Boolean if process has network activity
        - is_child: Boolean if process has parent
        """
        logger.info("Extracting features from process events...")
        
        conn = self.db._get_connection()
        
        # Build query
        query = '''
            SELECT 
                pid,
                name,
                cpu_percent,
                memory_mb,
                num_threads,
                connections_count,
                suspicious_score,
                parent_pid,
                timestamp
            FROM process_events
            WHERE cpu_percent IS NOT NULL
              AND memory_mb IS NOT NULL
              AND num_threads IS NOT NULL
        '''
        
        if limit:
            query += f' ORDER BY timestamp DESC LIMIT {limit}'
        
        # Load data
        df = pd.read_sql_query(query, conn)
        
        if len(df) == 0:
            raise ValueError("No process events found in database")
        
        logger.info(f"Loaded {len(df)} process events")
        
        # Feature engineering
        df['parent_pid_norm'] = df['parent_pid'].fillna(0).clip(0, 100000) / 100000  # Normalize PIDs
        df['has_network'] = (df['connections_count'] > 0).astype(int)
        df['is_child'] = (df['parent_pid'].notna()).astype(int)
        
        # Fill missing values
        df['cpu_percent'] = df['cpu_percent'].fillna(0)
        df['memory_mb'] = df['memory_mb'].fillna(0)
        df['num_threads'] = df['num_threads'].fillna(1)
        df['connections_count'] = df['connections_count'].fillna(0)
        df['suspicious_score'] = df['suspicious_score'].fillna(0)
        
        # Select feature columns
        feature_cols = [
            'cpu_percent',
            'memory_mb', 
            'num_threads',
            'connections_count',
            'parent_pid_norm',
            'has_network',
            'is_child'
        ]
        
        self.feature_names = feature_cols
        
        # Add target label based on suspicious_score
        df['label'] = self._auto_label(df['suspicious_score'])
        
        logger.info(f"Feature extraction complete. Shape: {df[feature_cols].shape}")
        
        return df[feature_cols + ['label', 'suspicious_score', 'name', 'pid']]
    
    def _auto_label(self, scores: pd.Series) -> pd.Series:
        """
        Auto-label events based on suspicious score thresholds
        
        Labels:
        - 1 (malicious): score >= 50
        - 0 (benign): score < 20
        - -1 (unlabeled/uncertain): 20 <= score < 50
        """
        labels = pd.Series(-1, index=scores.index)  # Default: unlabeled
        labels[scores >= 50] = 1  # Malicious
        labels[scores < 20] = 0   # Benign
        return labels
    
    def train_isolation_forest(self, X: np.ndarray) -> Dict[str, Any]:
        """
        Train Isolation Forest for unsupervised anomaly detection
        
        Returns dict with training metrics
        """
        logger.info("Training Isolation Forest...")
        
        if_config = self.ml_config.get('isolation_forest', {})
        
        self.isolation_forest = IsolationForest(
            n_estimators=if_config.get('n_estimators', 100),
            contamination=if_config.get('contamination', 0.1),
            random_state=self.training_config.get('random_state', 42),
            n_jobs=-1
        )
        
        # Train
        self.isolation_forest.fit(X)
        
        # Predict anomaly scores (-1 = anomaly, 1 = normal)
        predictions = self.isolation_forest.predict(X)
        anomaly_scores = self.isolation_forest.score_samples(X)
        
        # Calculate metrics
        anomaly_count = (predictions == -1).sum()
        anomaly_percent = (anomaly_count / len(predictions)) * 100
        
        metrics = {
            'model': 'IsolationForest',
            'total_samples': len(X),
            'anomalies_detected': int(anomaly_count),
            'anomaly_percentage': float(anomaly_percent),
            'mean_anomaly_score': float(anomaly_scores.mean()),
            'std_anomaly_score': float(anomaly_scores.std()),
            'min_anomaly_score': float(anomaly_scores.min()),
            'max_anomaly_score': float(anomaly_scores.max())
        }
        
        logger.info(f"Isolation Forest trained: {anomaly_count} anomalies ({anomaly_percent:.1f}%)")
        
        return metrics
    
    def train_random_forest(self, X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        """
        Train Random Forest classifier on labeled data
        
        Returns dict with classification metrics
        """
        logger.info("Training Random Forest classifier...")
        
        # Filter out unlabeled data (-1)
        labeled_mask = y != -1
        X_labeled = X[labeled_mask]
        y_labeled = y[labeled_mask]
        
        if len(X_labeled) < 100:
            logger.warning(f"Only {len(X_labeled)} labeled samples - may not train well")
        
        logger.info(f"Training on {len(X_labeled)} labeled samples")
        logger.info(f"  - Benign: {(y_labeled == 0).sum()}")
        logger.info(f"  - Malicious: {(y_labeled == 1).sum()}")
        
        # Split data
        test_size = self.training_config.get('test_size', 0.2)
        X_train, X_test, y_train, y_test = train_test_split(
            X_labeled, y_labeled,
            test_size=test_size,
            random_state=self.training_config.get('random_state', 42),
            stratify=y_labeled if len(np.unique(y_labeled)) > 1 else None
        )
        
        # Train Random Forest
        rf_config = self.ml_config.get('random_forest', {})
        
        self.random_forest = RandomForestClassifier(
            n_estimators=rf_config.get('n_estimators', 100),
            max_depth=rf_config.get('max_depth', 10),
            random_state=self.training_config.get('random_state', 42),
            n_jobs=-1
        )
        
        self.random_forest.fit(X_train, y_train)
        
        # Predictions
        y_pred = self.random_forest.predict(X_test)
        y_pred_proba = self.random_forest.predict_proba(X_test)
        
        # Calculate metrics
        accuracy = accuracy_score(y_test, y_pred)
        precision = precision_score(y_test, y_pred, average='binary', zero_division=0)
        recall = recall_score(y_test, y_pred, average='binary', zero_division=0)
        f1 = f1_score(y_test, y_pred, average='binary', zero_division=0)
        
        # Confusion matrix (handle single-class case)
        cm = confusion_matrix(y_test, y_pred)
        if cm.size == 1:
            # Single class - all benign or all malicious
            if y_test[0] == 0:  # All benign
                tn, fp, fn, tp = cm[0, 0], 0, 0, 0
            else:  # All malicious
                tn, fp, fn, tp = 0, 0, 0, cm[0, 0]
        else:
            tn, fp, fn, tp = cm.ravel()
        
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
        fnr = fn / (fn + tp) if (fn + tp) > 0 else 0
        
        # ROC AUC (if binary classification)
        try:
            if len(y_pred_proba.shape) > 1 and y_pred_proba.shape[1] == 2:
                roc_auc = roc_auc_score(y_test, y_pred_proba[:, 1])
            else:
                roc_auc = None
        except:
            roc_auc = None
        
        # Feature importance
        feature_importance = [
            {'feature': name, 'importance': float(importance)}
            for name, importance in zip(self.feature_names, self.random_forest.feature_importances_)
        ]
        feature_importance.sort(key=lambda x: x['importance'], reverse=True)
        
        metrics = {
            'model': 'RandomForest',
            'train_samples': len(X_train),
            'test_samples': len(X_test),
            'accuracy': float(accuracy),
            'precision': float(precision),
            'recall': float(recall),
            'f1_score': float(f1),
            'false_positive_rate': float(fpr),
            'false_negative_rate': float(fnr),
            'confusion_matrix': {
                'true_negatives': int(tn),
                'false_positives': int(fp),
                'false_negatives': int(fn),
                'true_positives': int(tp)
            },
            'feature_importance': feature_importance
        }
        
        if roc_auc is not None:
            metrics['roc_auc'] = float(roc_auc)
        
        logger.info(f"Random Forest trained - Accuracy: {accuracy:.3f}, F1: {f1:.3f}")
        
        return metrics
    
    def train(self, max_samples: int = None) -> Dict[str, Any]:
        """
        Full training pipeline
        
        Returns:
            Dict with training results and metrics
        """
        logger.info("=" * 60)
        logger.info("Starting ML Training Pipeline")
        logger.info("=" * 60)
        
        start_time = datetime.now()
        
        try:
            # 1. Extract features
            df = self.extract_features(limit=max_samples)
            
            min_samples = self.training_config.get('min_samples', 1000)
            if len(df) < min_samples:
                raise ValueError(f"Insufficient data: {len(df)} events (need {min_samples})")
            
            # 2. Prepare data
            X = df[self.feature_names].values
            y = df['label'].values
            
            # 3. Scale features
            logger.info("Scaling features...")
            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X)
            
            # 4. Train Isolation Forest (unsupervised)
            if self.ml_config.get('isolation_forest', {}).get('enabled', True):
                if_metrics = self.train_isolation_forest(X_scaled)
                self.metrics['isolation_forest'] = if_metrics
            
            # 5. Train Random Forest (supervised)
            if self.ml_config.get('random_forest', {}).get('enabled', True):
                rf_metrics = self.train_random_forest(X_scaled, y)
                self.metrics['random_forest'] = rf_metrics
            
            # 6. Save models
            self._save_models()
            
            # 7. Save metrics
            training_time = (datetime.now() - start_time).total_seconds()
            
            full_metrics = {
                'timestamp': datetime.now().isoformat(),
                'training_time_seconds': training_time,
                'total_samples': len(df),
                'features': self.feature_names,
                'label_distribution': {
                    'benign': int((y == 0).sum()),
                    'malicious': int((y == 1).sum()),
                    'unlabeled': int((y == -1).sum())
                },
                'models': self.metrics
            }
            
            self._save_metrics(full_metrics)
            
            logger.info("=" * 60)
            logger.info(f"Training complete in {training_time:.1f}s")
            logger.info("=" * 60)
            
            return {
                'status': 'success',
                'metrics': full_metrics
            }
            
        except Exception as e:
            logger.error(f"Training failed: {e}", exc_info=True)
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    def _save_models(self):
        """Save trained models to disk"""
        logger.info("Saving models...")
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save Isolation Forest
        if self.isolation_forest:
            if_path = self.models_dir / f'isolation_forest_{timestamp}.pkl'
            with open(if_path, 'wb') as f:
                pickle.dump(self.isolation_forest, f)
            logger.info(f"Saved Isolation Forest: {if_path}")
            
            # Also save as 'latest'
            latest_if = self.models_dir / 'isolation_forest_latest.pkl'
            with open(latest_if, 'wb') as f:
                pickle.dump(self.isolation_forest, f)
        
        # Save Random Forest
        if self.random_forest:
            rf_path = self.models_dir / f'random_forest_{timestamp}.pkl'
            with open(rf_path, 'wb') as f:
                pickle.dump(self.random_forest, f)
            logger.info(f"Saved Random Forest: {rf_path}")
            
            # Also save as 'latest'
            latest_rf = self.models_dir / 'random_forest_latest.pkl'
            with open(latest_rf, 'wb') as f:
                pickle.dump(self.random_forest, f)
        
        # Save scaler
        if self.scaler:
            scaler_path = self.models_dir / f'scaler_{timestamp}.pkl'
            with open(scaler_path, 'wb') as f:
                pickle.dump(self.scaler, f)
            
            latest_scaler = self.models_dir / 'scaler_latest.pkl'
            with open(latest_scaler, 'wb') as f:
                pickle.dump(self.scaler, f)
            logger.info(f"Saved scaler: {scaler_path}")
    
    def _save_metrics(self, metrics: Dict):
        """Save training metrics to JSON"""
        metrics_file = self.metrics_dir / 'latest_metrics.json'
        
        with open(metrics_file, 'w') as f:
            json.dump(metrics, f, indent=2)
        
        logger.info(f"Saved metrics: {metrics_file}")
        
        # Also save timestamped copy
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        archive_file = self.metrics_dir / f'metrics_{timestamp}.json'
        with open(archive_file, 'w') as f:
            json.dump(metrics, f, indent=2)


def main():
    """Standalone training script"""
    import yaml
    import argparse
    
    parser = argparse.ArgumentParser(description='Train EDR ML models')
    parser.add_argument('--config', default='config/config.yaml', help='Config file path')
    parser.add_argument('--max-samples', type=int, help='Max samples to use for training')
    parser.add_argument('--verbose', action='store_true', help='Verbose logging')
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Load config
    with open(args.config, 'r') as f:
        config = yaml.safe_load(f)
    
    # Import database
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from utils.db_v2 import EDRDatabase
    
    # Initialize
    db = EDRDatabase(
        db_path=config['paths']['database'],
        nas_backup_path=config['paths'].get('nas_backups')
    )
    
    pipeline = MLTrainingPipeline(config, db)
    
    # Train
    result = pipeline.train(max_samples=args.max_samples)
    
    if result['status'] == 'success':
        print("\n✅ Training completed successfully!")
        print(f"\nMetrics saved to: {pipeline.metrics_dir / 'latest_metrics.json'}")
        print(f"Models saved to: {pipeline.models_dir}")
    else:
        print(f"\n❌ Training failed: {result['error']}")
        sys.exit(1)


if __name__ == '__main__':
    main()
