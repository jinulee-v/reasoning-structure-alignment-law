/* ========= RULES FROM THE STATUTE (only the parts that are relevant
            to this concrete case were encoded) ===================== */

/* -------------------- general flight data ------------------------ */
flight(elizabeth, salt_lake_city, charlotte).
class(elizabeth, premium_economy).
ticket_price(elizabeth, 66).

within_us(salt_lake_city,charlotte).   /* the itinerary is totally inside U.S. */

/* -------------------- allowances --------------------------------- */
free_checked_bags(premium_economy, 2).

/* checked-bag fee that depends on the bag number
   (only for itineraries totally inside the U.S.)                   */
checked_bag_fee(_Class, BagNumber, 0)      :- BagNumber =< 2.            /* 1st - 2nd */
checked_bag_fee(_Class, 3,          150).                               /* 3rd        */
checked_bag_fee(_Class, N,          200) :- N >= 4.                     /* 4th +      */

/* -------------------- overweight fees (within U.S.) -------------- */
overweight_fee(Weight, 0)  :- Weight =< 50.
overweight_fee(Weight, 30) :- Weight  > 50, Weight =< 53.
overweight_fee(Weight, 100):- Weight  > 53, Weight =< 70.
overweight_fee(Weight, 200):- Weight  > 70, Weight =< 100.

/* -------------------- oversize fees (within U.S.) ---------------- */
oversize_fee(Size, 0)   :- Size     =< 62.
oversize_fee(Size, 30)  :- Size     > 62, Size =< 65.
oversize_fee(Size, 200) :- Size     > 65, Size =< 115.

/* for one bag the higher amount between oversize and overweight
   applies (in addition to any checked-bag fee)                     */
extra_size_weight_fee(Weight,Size,Fee) :-
    overweight_fee(Weight,OW), oversize_fee(Size,OS),
    ( OW >= OS -> Fee = OW ; Fee = OS).

/* ========== FACTS THAT DESCRIBE ELIZABETH'S BAGS ================= */

/* bag(Id, Length, Width, Height, Weight).  */
bag(1, 41,21,16, 57).
bag(2, 38,16, 9, 66).
bag(3, 37,14,12, 52).
bag(4, 38,12,13, 55).

/* turn the physical data of a bag into its fees ------------------- */
one_bag_total_cost(BagNumber, Weight, L,W,H, Cost) :-
    Size is L+W+H,
    checked_bag_fee(premium_economy, BagNumber, BagFee),
    extra_size_weight_fee(Weight, Size, ExtraFee),
    Cost is BagFee + ExtraFee.

/* ========== TOTAL COST FOR THE TRIP ============================== */
total_bag_cost(Total) :-
    findall(Cost,
            ( bag(Index,L,W,H,Weight),
              nth1(BagNumber,[1,2,3,4],Index),  % bag order as given
              one_bag_total_cost(BagNumber,Weight,L,W,H,Cost)
            ),
            Costs),
    sumlist(Costs, Total).

total_cost(Total) :-
    ticket_price(elizabeth,Ticket),
    total_bag_cost(BagCost),
    Total is Ticket + BagCost.

/* ======================= QUERY =================================== */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.