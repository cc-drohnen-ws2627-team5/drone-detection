import matplotlib.pyplot as plt
import numpy as np

# 1. Rekonstruierte Konfusionsmatrix (als Numpy-Array)
# Zeilen: Tatsächliche Klassen (Ground Truth), Spalten: Vorhersagen
# [Drohne, Hintergrund]
conf_matrix = np.array([
    [331, 38],  # Tatsächliche Drohnen (369 gesamt: 331 erkannt, 38 übersehen)
    [ 22,  0]   # Hintergrund / False Positives (22 Fehlalarme)
])

# Plotten der Konfusionsmatrix
fig, ax = plt.subplots(figsize=(6, 5))
cax = ax.matshow(conf_matrix, cmap=plt.cm.Blues, alpha=0.7)

for (i, j), val in np.ndenumerate(conf_matrix):
    ax.text(j, i, f"{val}", ha='center', va='center', fontsize=14, fontweight='bold')

plt.title('Rekonstruierte Konfusionsmatrix (Drohnen-Erkennung)', pad=20, fontsize=12, fontweight='bold')
plt.xlabel('Vorhergesagte Klasse', fontsize=10)
plt.ylabel('Tatsächliche Klasse (Ground Truth)', fontsize=10)
ax.set_xticks([0, 1])
ax.set_yticks([0, 1])
ax.set_xticklabels(['Drohne', 'Hintergrund'])
ax.set_yticklabels(['Drohne', 'Hintergrund'])
plt.colorbar(cax)
plt.tight_layout()
plt.show()


# 2. Statischer Plot des Trainingsverlaufs (Ausgewählte Epochen aus den Logs)
epochs = [1, 10, 25, 50, 75, 79, 100]
mAP50  = [0.568, 0.679, 0.749, 0.868, 0.910, 0.945, 0.923]
box_loss = [1.416, 1.330, 1.166, 1.001, 0.888, 0.849, 0.576]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))

# mAP@0.5 Verlauf
ax1.plot(epochs, mAP50, marker='o', color='b', linestyle='-')
ax1.set_title('mAP@0.5 über ausgewählte Epochen')
ax1.set_xlabel('Epoche')
ax1.set_ylabel('mAP@0.5')
ax1.grid(True)

# Box Loss Verlauf
ax2.plot(epochs, box_loss, marker='s', color='r', linestyle='-')
ax2.set_title('Box Loss über ausgewählte Epochen')
ax2.set_xlabel('Epoche')
ax2.set_ylabel('Box Loss')
ax2.grid(True)

plt.tight_layout()
plt.show()