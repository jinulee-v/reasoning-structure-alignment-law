/* --------------  Statutory rules we need for this case -------------- */

% route type for this itinerary
route(within_us).

% passenger fare class
fare_class(main_plus).

% the ticket price
flight_ticket_cost(216).

/* Main Plus gives 1 extra free checked bag (in addition to the Main-Cabin
   allowance which is otherwise 0 on domestic itineraries). */
free_checked_bags(1).

/* ---------- base checked-bag fees on a domestic itinerary ----------- */
/* Index = sequential number of the checked bag AFTER applying the
           complimentary-bag allowance                            */
bag_base_fee(1, 45).      %  "2nd" bag fee
bag_base_fee(2, 150).     %  "3rd" bag fee
bag_base_fee(N, 200) :-   %  "4th +" bag fee
    N >= 3.

/* -----------------  over-weight / over-size charges ----------------- */

% oversize fee (length+width+height = S)
oversize_fee(S, 0)   :- S =< 62.
oversize_fee(S, 30)  :- S > 62, S =< 65.
oversize_fee(S, 200) :- S > 65, S =< 115.

% overweight fee (Weight = W, domestic itinerary)
overweight_fee(W, 0)    :- W =< 50.
overweight_fee(W, 30)   :- W > 50, W =< 53.
overweight_fee(W, 100)  :- W > 53, W =< 70.
overweight_fee(W, 200)  :- W > 70, W =< 100.

% for a bag that is both oversize and overweight, only the higher fee applies
extra_fee(DimSum,Weight,Fee) :-
    oversize_fee(DimSum,OFee),
    overweight_fee(Weight,WFee),
    (OFee >= WFee -> Fee = OFee ; Fee = WFee).

/* ---------------------------  the bags ------------------------------ */
/* checked_bag(Index, L, W, H, Weight).  (personal item not listed) */
checked_bag(1, 37, 12, 14, 52).   % backpack
checked_bag(2, 33, 17, 14, 62).   % luggage box
checked_bag(3, 44, 21, 16, 51).   % backpack
checked_bag(4, 50, 35, 24, 83).   % backpack

/* -----------------  cost for each individual bag  ------------------ */

% sequential number of paid bag after the free-bag allowance
paid_index(BagIndex,PaidIdx) :-
    free_checked_bags(Free),
    PaidIdx is BagIndex - Free,
    PaidIdx >= 1.

% base fee for a bag (0 if within the free allowance)
bag_base_cost(BagIndex,0) :-
    free_checked_bags(Free),
    BagIndex =< Free.
bag_base_cost(BagIndex,Cost) :-
    paid_index(BagIndex,PaidIdx),
    bag_base_fee(PaidIdx,Cost).

% total charge for one bag = base fee + extra (oversize / overweight)
bag_total_cost(BagIndex,Total) :-
    checked_bag(BagIndex,L,W,H,Weight),
    DimSum is L+W+H,
    extra_fee(DimSum,Weight,Extra),
    bag_base_cost(BagIndex,Base),
    Total is Base + Extra.

/* -----------------------  overall total  --------------------------- */

bags_total_cost(Sum) :-
    findall(C, (checked_bag(I,_,_,_,_), bag_total_cost(I,C)), Costs),
    sum_list(Costs,Sum).

total_cost(Total) :-
    flight_ticket_cost(Ticket),
    bags_total_cost(Bags),
    Total is Ticket + Bags.

/* ---------------------------  query  -------------------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.