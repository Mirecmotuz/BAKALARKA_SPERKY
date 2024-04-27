import numpy as np
import pandas as pd
from scipy.optimize import milp
from scipy.optimize import LinearConstraint
from scipy.optimize import Bounds

pd.set_option("display.max_rows", None, "display.max_columns", None, "display.width", None)

class Distribucia:
    def __init__(self):
        self.udaje_sperky = pd.read_excel("distribucia_vstupne_udaje.xlsx")


    def podmienky_obmedzenia_skladov(self, matica_obmedzeni: list, dolne_medze: list, horne_medze: list) -> tuple:
        """
        vytvori subor podmienok, ktore zabrania naskladneniu viacej sperkov na butik, ako je povolene limitom
        :param matica_obmedzeni: predosle obmedzenia
        :param dolne_medze: prdosle dolne medze
        :param horne_medze: predosle horne medze
        :return: upravene data
        """

        for butik in range(1, 15):
            obmedzenie_butik = []
            indexy_butik = list(self.udaje_sperky.loc[self.udaje_sperky["butik"] == butik].index)

            for index, riadok in self.udaje_sperky.iterrows():
                if index in indexy_butik:
                    obmedzenie_butik.append(1)
                else:
                    obmedzenie_butik.append(0)

            matica_obmedzeni.append(obmedzenie_butik)
            dolne_medze.append(0)
            horne_medze.append(self.butiky_limity_indexy[butik])

        return matica_obmedzeni, dolne_medze, horne_medze

    def podmienky_naskladnenia_vsetkeho(self, matica_obmedzeni: list, dolne_medze: list, horne_medze: list) -> tuple:
        """
        podmienka zaruci, kazdy sperk bude prideleny presne na 1 butik
        pri podmienke tykajucej sa konkretneho sperku priradi do obmedzenia ku premennym popisujucim
        konkretny sperk pridany ku inym butikov jednotku a ku ostatnym 0. lava medza bude 1 a prava tiez 1.
        To mi zaruci rovnost 1

        :param matica_obmedzeni: matica pridanych obmedzeni
        :param dolne_medze: vektor dolnych medzi
        :param horne_medze: vektor hornych medzi
        :return: upravene zoznamy
        """
        sperky = list(self.udaje_sperky["sperk"].unique())

        for sperk in sperky:
            obmedzenie_sperku = []
            for index, riadok in self.udaje_sperky.iterrows():
                if riadok["sperk"] == sperk:
                    obmedzenie_sperku.append(1)
                else:
                    obmedzenie_sperku.append(0)

            matica_obmedzeni.append(obmedzenie_sperku)
            dolne_medze.append(1)
            horne_medze.append(1)

        return matica_obmedzeni, dolne_medze, horne_medze


    def optimize_new(self, alpha: float, beta: float, skladove_obmezenia: dict):
        """
        vytvori zo vstupnych dat vektor cien pre vektor hodnotiacich premennych, vytvori potrebne podmienky a obmedzenia
        aby sme naskladnili kazdy sperk iba na jeden butik, vytvori obmedzenia pre sklady a podmienky zarucujuce
        funkcnost penalizacnych faktorov v ucelovej funkcii. Vsetko to spracuje do formy, ktoru mozme vlozit do
        funkcie milp, ktora vyriesi nas binarny problem
        :return:
        """
        self.butiky_limity_indexy = skladove_obmezenia
        hodnoty_ucelovej_funkcie = list(self.udaje_sperky["faktor_c"])

        matica_obmedzeni = []
        dolne_medze = []
        horne_medze = []

        matica_obmedzeni, dolne_medze, horne_medze = self.podmienky_naskladnenia_vsetkeho(matica_obmedzeni, dolne_medze,
                                                                                          horne_medze)

        matica_obmedzeni, dolne_medze, horne_medze = self.podmienky_obmedzenia_skladov(matica_obmedzeni, dolne_medze,
                                                                                     horne_medze)
        print("penalizacia ID")
        #penalizacia ID
        (matica_obmedzeni, dolne_medze,
         horne_medze, hodnoty_ucelovej_funkcie) = self.penalizacia("ID", 1, 5, hodnoty_ucelovej_funkcie,
                                                                    matica_obmedzeni, dolne_medze, horne_medze)
        print("penalizacia 10")
        #penalizacia 10
        (matica_obmedzeni, dolne_medze,
         horne_medze, hodnoty_ucelovej_funkcie) = self.penalizacia("10", 3/4, 8, hodnoty_ucelovej_funkcie,
                                                                   matica_obmedzeni, dolne_medze, horne_medze)
        print("penalizacia 9")
        #penalizcia 9
        (matica_obmedzeni, dolne_medze,
         horne_medze, hodnoty_ucelovej_funkcie) = self.penalizacia("9", 1/2, 8, hodnoty_ucelovej_funkcie,
                                                                   matica_obmedzeni, dolne_medze, horne_medze)

        print(f"riadky matice A {len(matica_obmedzeni)}")
        print(f"stlpce matice A {len(matica_obmedzeni[0])}")

        obmedzenia = LinearConstraint(matica_obmedzeni, dolne_medze, horne_medze)

        celociselnost = [1] * len(hodnoty_ucelovej_funkcie)

        # obmedzenia rozhodovacich premennych
        dolne_obmedzenie = [0] * len(hodnoty_ucelovej_funkcie)
        horne_obmedzenie = [1] * len(hodnoty_ucelovej_funkcie)
        obmedzenia_rozhodovacich_premennych = Bounds(lb=dolne_obmedzenie, ub=horne_obmedzenie)

        #musime obratit hodnoty ucelovej funkcie aby sme mali maximalizaciu
        hodnoty_ucelovej_funkcie = [-hodnota for hodnota in hodnoty_ucelovej_funkcie]

        optimalizovane_hodnoty = milp(c=hodnoty_ucelovej_funkcie,
                                      constraints=obmedzenia,
                                      integrality=celociselnost,
                                      bounds=obmedzenia_rozhodovacich_premennych,
                                      options={"disp": True, "presolve": True})


        optimalizovane_hodnoty = list(optimalizovane_hodnoty.x)[:self.udaje_sperky.shape[0]]

        self.udaje_sperky["rozdelenie"] = optimalizovane_hodnoty

        print(self.udaje_sperky)


    def penalizacia(self, typ: str, koeficient: float, iteracie: int, hodnoty_ucelovej_funkcie: list,
                    matica_obmedzeni: list, dolne_medze: list, horne_medze) -> tuple:
        """
        do ucelovej funkcie zada penalizacne faktory a vytvori obmedzenia pre premenne nutne na penalizaciu
        :param typ: ci idem penalizovat "ID" alebo "10", alebo "9"
        :param koeficient: znizuje penalizaciu ak nepenalizujem pomocou ID, teda je rozdielny od 1 iba ak mam penalizaciu 10 alebo 9
        :param iteracie: v modeli to oznacuje, kolko sperkov maximalne naskladnujem z daneho typu(podobnosti)
        :param hodnoty_ucelovej_funkcie:
        :param matica_obmedzeni:
        :param dolne_medze:
        :param horne_medze:
        :return: upravene hodnoty
        """

        IDcka = list(self.udaje_sperky["ID"].unique())

        print(len(IDcka))
        for poradie, ID in enumerate(IDcka):
            print(poradie)

            for butik in range(1, 15):

                dolezitost = list(self.udaje_sperky.loc[(self.udaje_sperky["ID"] == ID) &
                                                   (self.udaje_sperky["butik"] == butik), "faktor_c"])[0]
                faktor = dolezitost * koeficient

                for r in range(1, iteracie + 1):
                    penalizacia = -faktor * (r/(r + 1))
                    #pridam hodnotu do ucelovej funkcie
                    hodnoty_ucelovej_funkcie.append(penalizacia)

                    posledny_index = len(hodnoty_ucelovej_funkcie) - 1
                    obmedzenie_1 = []
                    obmedzenie_2 = []
                    if typ == "ID":
                        indexy_podobnych = list(self.udaje_sperky.loc[(self.udaje_sperky["ID"] == ID) &
                                                                                (self.udaje_sperky["butik"]) == butik].index)
                        #indexy_rovnaky_butik_rovnake_ID

                    elif typ == "10":
                        podobnost_10 = ID[:10]

                        indexy_podobnych = list(self.udaje_sperky.loc[(self.udaje_sperky["podobnost_10"] == podobnost_10) &
                                                                                (self.udaje_sperky["butik"] == butik) &
                                                                      (self.udaje_sperky["ID"] != ID)].index)
                        #indexy_rovnaky_butik_rovnake_10 bez ID
                    elif typ == "9":
                        podobnost_9 = ID[:9]
                        podobnost_10 = ID[:10]
                        indexy_podobnych = list(
                            self.udaje_sperky.loc[(self.udaje_sperky["podobnost_9"] == podobnost_9) &
                                                  (self.udaje_sperky["butik"] == butik) &
                                                  (self.udaje_sperky["podobnost_10"] != podobnost_10)].index)
                        #indexy_rovnaky_butik_rovnake_9 bez 10 a ID
                    else:
                        raise Exception("Zadal si zly typ.")

                    indexy_s_nulami = np.setdiff1d(list(range(len(hodnoty_ucelovej_funkcie))), [*indexy_podobnych, posledny_index])

                    #medze 1. podmienka
                    dolne_medze.append(-np.inf)
                    horne_medze.append(r)

                    #obmezdenia 1. podmienka

                    for index in range(len(hodnoty_ucelovej_funkcie)):
                        if index in indexy_s_nulami:
                            obmedzenie_1.append(0)
                        else:
                            if index in indexy_podobnych:
                                obmedzenie_1.append(1)
                            elif index == posledny_index:
                                obmedzenie_1.append(-1984)
                            else:
                                raise Exception("Mas divne indexy")
                    matica_obmedzeni.append(obmedzenie_1)

                    #medze 2. podmienka
                    dolne_medze.append(-np.inf)
                    horne_medze.append(-(r + 1) + 1984)

                    # obmezdenia 2. podmienka
                    for index in range(len(hodnoty_ucelovej_funkcie)):
                        if index in indexy_s_nulami:
                            obmedzenie_2.append(0)
                        else:
                            if index in indexy_podobnych:
                                obmedzenie_2.append(-1)
                            elif index == posledny_index:
                                obmedzenie_2.append(1984)
                            else:
                                raise Exception("Mas divne indexy")
                    matica_obmedzeni.append(obmedzenie_2)

        #doplnim nuly nakoniec aby mali obmedzenia rovnako clenov
        if typ == '9':
            nova_matica = []
            pocet_prvkov_posledneho = len(matica_obmedzeni[len(matica_obmedzeni) - 1])
            for obmedzenie in matica_obmedzeni:
                if len(obmedzenie) < pocet_prvkov_posledneho:
                    nove_nuly = [0] * (pocet_prvkov_posledneho - len(obmedzenie))
                    nove_obmedzenie = [*obmedzenie, *nove_nuly]
                    nova_matica.append(nove_obmedzenie)
                else:#priradim podledne obmedzenie
                    nova_matica.append(obmedzenie)

            return nova_matica, dolne_medze, horne_medze, hodnoty_ucelovej_funkcie
        else:
            return matica_obmedzeni, dolne_medze, horne_medze, hodnoty_ucelovej_funkcie




if __name__ == "__main__":
    skladove_limity = {1: 100, 2: 100, 3: 100, 4: 100, 5: 100, 6: 100, 7: 100,
                        8: 20, 9: 20, 10: 20, 11: 20, 12: 20, 13: 20, 14: 20}
    dist = Distribucia()
    dist.optimize_new(alpha = 3/4, beta = 1/2, skladove_obmezenia = skladove_limity)

    #nastavenim parametrov alfa, beta a skladove_limity menime obmedzenia v modeli


